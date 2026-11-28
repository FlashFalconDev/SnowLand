import { Buffer } from "node:buffer";
import { createHmac, timingSafeEqual } from "node:crypto";

const MAX_BODY_BYTES = 1024 * 1024;
const MAX_MEDIA_BYTES = 50 * 1024 * 1024;
const DEFAULT_RELAY_BYTES = 24 * 1024;
const HARD_MAX_RELAY_BYTES = 512 * 1024;
const RECENT_LIMIT = 10;
const RECENT_TEXT_LIMIT = 2000;
const OLDER_TEXT_LIMIT = 200;
const PROFILE_TTL_SECONDS = 86400;
const PROFILE_TIMEOUT_MS = 2000;
const MEDIA_TTL_SECONDS = 3600;
const HISTORY_TTL_SECONDS = 172800;
const HISTORY_LIMIT = 50;
const HISTORY_TIME_MAX = 999_999_999_999_999;
const HISTORY_TIME_WIDTH = 15;
const HISTORY_PAGE_SIZE = 100;
const MAX_HISTORY_PAGES = 20;
const TAIPEI_OFFSET_MS = 8 * 60 * 60 * 1000;
const LINE_SIGNATURE_LENGTH = 44;
const MEDIA_PATH = "/media/";
const MEDIA_TYPES = new Set(["image", "video", "file"]);
const graphemes = new Intl.Segmenter("und", { granularity: "grapheme" });
const decoder = new TextDecoder("utf-8", { fatal: true });

async function readBody(body, maxBytes) {
  if (!body) return Buffer.alloc(0);

  const reader = body.getReader();
  const chunks = [];
  let size = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return Buffer.concat(chunks, size);

      size += value.byteLength;
      if (size > maxBytes) {
        void reader.cancel().catch(() => {});
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
}

function hasValidLineSignature(signature, body, secret) {
  if (!secret || signature?.length !== LINE_SIGNATURE_LENGTH) return false;

  const expected = createHmac("sha256", secret).update(body).digest("base64");
  const receivedBytes = Buffer.from(signature);
  const expectedBytes = Buffer.from(expected);
  return receivedBytes.length === expectedBytes.length &&
    timingSafeEqual(receivedBytes, expectedBytes);
}

function positiveInteger(value, fallback) {
  const number = Number(value);
  return Number.isSafeInteger(number) && number > 0 ? number : fallback;
}

function unixSeconds() {
  return Math.floor(Date.now() / 1000);
}

function sanitizeId(id) {
  return id.replace(/[^A-Za-z0-9_-]/g, "_");
}

function mediaSignature(secret, key, exp) {
  return createHmac("sha256", secret).update(`media\n${key}\n${exp}`).digest("hex");
}

async function downloadMedia(url, env) {
  if (!env.RELAY_SIGNING_SECRET || !env.MEDIA_BUCKET) {
    return new Response(null, { status: 503 });
  }

  let key;
  try {
    key = decodeURIComponent(url.pathname.slice(MEDIA_PATH.length));
  } catch {
    return new Response(null, { status: 400 });
  }
  if (!key.startsWith("line-media/") || key.includes("..") || key.includes("\\")) {
    return new Response(null, { status: 400 });
  }

  const exp = url.searchParams.get("exp");
  const sig = url.searchParams.get("sig");
  if (!exp || /[^0-9]/.test(exp) || !Number.isSafeInteger(Number(exp)) ||
      unixSeconds() > Number(exp) || sig?.length !== 64 || /[^0-9a-f]/.test(sig)) {
    return new Response(null, { status: 403 });
  }
  const expected = mediaSignature(env.RELAY_SIGNING_SECRET, key, exp);
  if (!timingSafeEqual(Buffer.from(sig, "hex"), Buffer.from(expected, "hex"))) {
    return new Response(null, { status: 403 });
  }

  try {
    const object = await env.MEDIA_BUCKET.get(key);
    if (!object) return new Response(null, { status: 404 });

    return new Response(object.body, {
      headers: {
        "Content-Type": object.httpMetadata?.contentType || "application/octet-stream",
        "Content-Disposition": "attachment",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch {
    console.warn("Media storage read failed");
    return new Response(null, { status: 503 });
  }
}

async function storeMedia(message, groupId, taipeiDate, env) {
  const media = {
    type: message.type,
    contentType: null,
    size: null,
    duration: typeof message.duration === "number" ? message.duration : null,
    r2Key: null,
  };

  if (!env.LINE_CHANNEL_ACCESS_TOKEN) return { ...media, status: "skipped_missing_token" };
  if (!env.MEDIA_BUCKET) return { ...media, status: "skipped_no_bucket" };

  const maxBytes = positiveInteger(env.MEDIA_MAX_BYTES, MAX_MEDIA_BYTES);
  let bytes;
  try {
    const response = await fetch(
      `https://api-data.line.me/v2/bot/message/${encodeURIComponent(message.id)}/content`,
      {
        method: "GET",
        redirect: "manual",
        headers: { Authorization: `Bearer ${env.LINE_CHANNEL_ACCESS_TOKEN}` },
      },
    );
    if (!response.ok) {
      void response.body?.cancel().catch(() => {});
      return { ...media, status: "download_failed" };
    }

    media.contentType = response.headers.get("Content-Type") || "application/octet-stream";
    if (Number(response.headers.get("Content-Length")) > maxBytes) {
      void response.body?.cancel().catch(() => {});
      return { ...media, status: "skipped_too_large" };
    }

    bytes = await readBody(response.body, maxBytes);
    if (bytes === null) return { ...media, status: "skipped_too_large" };
  } catch {
    return { ...media, status: "download_failed" };
  }

  media.size = bytes.byteLength;
  const key = `line-media/${taipeiDate}/${sanitizeId(groupId)}/${sanitizeId(message.id)}`;
  try {
    await env.MEDIA_BUCKET.put(key, bytes, {
      httpMetadata: { contentType: media.contentType },
      customMetadata: { messageId: message.id, mediaType: message.type, taipeiDate },
    });
    return { ...media, r2Key: key, status: "stored" };
  } catch {
    console.warn("Media storage write failed");
    return { ...media, status: "storage_failed" };
  }
}

async function readHistoryPrefix(kv, prefix, triggerIds, limit = Infinity) {
  const records = new Map();
  if (!kv) return { records, interrupted: false };

  try {
    let cursor;
    for (let page = 0; page < MAX_HISTORY_PAGES; page++) {
      const result = await kv.list({ prefix, cursor, limit: Math.min(HISTORY_PAGE_SIZE, limit - records.size) });
      if (result.keys.length > 0) {
        const values = await kv.get(result.keys.map(({ name }) => name), "json");
        for (const { name } of result.keys) {
          const record = values.get(name);
          if (record && !triggerIds.has(record.messageId) && !records.has(record.messageId)) {
            records.set(record.messageId, record);
          }
        }
      }
      if (records.size === limit || result.list_complete) return { records, interrupted: false };
      if (!result.cursor || result.cursor === cursor) break;
      cursor = result.cursor;
    }
  } catch {
    console.warn("Chat history read failed");
  }
  return { records, interrupted: true };
}

async function readHistory(kv, keyScope, triggerIds, limit) {
  const newest = await readHistoryPrefix(kv, `msgr:${keyScope}`, triggerIds, limit);
  // Remove the legacy scan once every old writer has stopped for at least the 48-hour TTL.
  const legacy = await readHistoryPrefix(kv, `msg:${keyScope}`, triggerIds);
  for (const [id, record] of legacy.records) {
    if (!newest.records.has(id)) newest.records.set(id, record);
  }
  return { records: newest.records, interrupted: newest.interrupted || legacy.interrupted };
}

function contextItem(record, triggerId, origin, exp, env) {
  const { media, fileName, ...fields } = record;
  const taipeiTime = new Date(record.timestampMs + TAIPEI_OFFSET_MS).toISOString().slice(0, 19).replace("T", " ");
  const item = { ...fields, taipeiTime, isTrigger: record.messageId === triggerId };
  if (media) {
    const { r2Key, ...metadata } = media;
    if (fileName != null) item.fileName = fileName;
    item.media = metadata;
    if (r2Key && !env.MEDIA_BUCKET) {
      item.media.status = "skipped_no_bucket";
    } else if (r2Key && env.RELAY_SIGNING_SECRET) {
      const sig = mediaSignature(env.RELAY_SIGNING_SECRET, r2Key, exp);
      item.downloadUrl = `${origin}${MEDIA_PATH}${encodeURIComponent(r2Key)}?exp=${exp}&sig=${sig}`;
    }
  }
  return item;
}

function limitText(item, limit) {
  const { text } = item;
  if (typeof text !== "string" || text.length <= limit) return item;

  let count = 0;
  for (const { segment, index } of graphemes.segment(text)) {
    count += [...segment].length;
    if (count > limit) return { ...item, text: text.slice(0, index), textTruncated: true };
  }
  return item;
}

async function readSenderName(userId, groupId, env) {
  if (typeof userId !== "string" || !userId || !env.LINE_CHANNEL_ACCESS_TOKEN || !env.CHAT_HISTORY) return;

  const controller = new AbortController();
  let timer;
  const deadline = new Promise((resolve) => {
    timer = setTimeout(() => {
      resolve(undefined);
      controller.abort();
    }, PROFILE_TIMEOUT_MS);
  });
  const lookup = async () => {
    const key = `profile:${sanitizeId(groupId)}:${sanitizeId(userId)}`;
    const cached = await env.CHAT_HISTORY.get(key, "text");
    if (controller.signal.aborted) return;
    if (typeof cached === "string" && cached.trim()) return cached;

    const response = await fetch(
      `https://api.line.me/v2/bot/group/${encodeURIComponent(groupId)}/member/${encodeURIComponent(userId)}`,
      {
        method: "GET",
        redirect: "manual",
        headers: { Authorization: `Bearer ${env.LINE_CHANNEL_ACCESS_TOKEN}` },
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      void response.body?.cancel().catch(() => {});
      return;
    }
    const profile = await response.json();
    if (controller.signal.aborted) return;
    const displayName = profile?.displayName;
    if (typeof displayName !== "string" || !displayName.trim()) return;
    await env.CHAT_HISTORY.put(key, displayName, { expirationTtl: PROFILE_TTL_SECONDS });
    return displayName;
  };

  try {
    // Bound the optional enrichment even if KV or the response body stalls.
    return await Promise.race([lookup(), deadline]);
  } catch {
    return undefined;
  } finally {
    clearTimeout(timer);
  }
}

function relayBody(fields, recent, context, groupFields, truncatedReasons, maxBytes) {
  const priority = { recent, recentCount: recent.length };
  const [trigger, ...older] = context;
  // Merging the fixed fields and metadata replaces two adjacent braces with one comma.
  const fixedBytes = Buffer.byteLength(JSON.stringify({
    ...fields,
    ...priority,
    ...groupFields,
    context: [trigger],
  })) - 1;
  const sizes = older.map((item) => Buffer.byteLength(JSON.stringify(item)) + 1);
  let olderBytes = sizes.reduce((total, size) => total + size, 0);
  const metadata = () => ({
    summary: `觸發前最新 ${recent.length} 則見 recent；較舊 ${older.length} 則在 context` +
      (truncatedReasons.length ? `；原因：${truncatedReasons.join("、")}` : ""),
    truncated: truncatedReasons.length > 0,
    ...(truncatedReasons.length > 0 ? { truncatedReasons } : {}),
    contextCount: 1 + recent.length + older.length,
  });
  const bytes = () => fixedBytes + Buffer.byteLength(JSON.stringify(metadata())) + olderBytes;

  if (bytes() > maxBytes) truncatedReasons.push("payload_limit");
  while (older.length > 0 && bytes() > maxBytes) {
    older.pop();
    olderBytes -= sizes.pop();
  }

  const finalBytes = bytes();
  if (finalBytes > HARD_MAX_RELAY_BYTES) return null;
  if (finalBytes > maxBytes) console.warn("Relay payload exceeds preferred size limit");

  const { summary, ...details } = metadata();
  return JSON.stringify({ summary, ...fields, ...priority, ...details, ...groupFields, context: [trigger, ...older] });
}

async function forwardEvent(trigger, group, history, origin, env) {
  try {
    const candidates = history.records.filter(({ messageId }) => messageId !== trigger.messageId);
    const selected = candidates.filter(({ timestampMs }) => timestampMs < trigger.timestampMs)
      .slice(0, history.limit)
      .sort((a, b) => b.timestampMs - a.timestampMs ||
        (a.messageId === b.messageId ? 0 : a.messageId < b.messageId ? -1 : 1));
    const recentRecords = selected.slice(0, RECENT_LIMIT);
    const userIds = new Set([trigger, ...recentRecords].map(({ userId }) => userId));
    const names = new Map(await Promise.all([...userIds].map(async (userId) =>
      [userId, await readSenderName(userId, group.groupId, env)])));

    const t = unixSeconds();
    const exp = t + positiveInteger(env.MEDIA_URL_TTL_SECONDS, MEDIA_TTL_SECONDS);
    const makeItem = (record) => contextItem(record, trigger.messageId, origin, exp, env);
    const recent = recentRecords.map((record) => {
      const item = makeItem(record);
      item.text ??= null;
      const senderName = names.get(record.userId);
      if (senderName) item.senderName = senderName;
      return limitText(item, RECENT_TEXT_LIMIT);
    });
    const senderName = names.get(trigger.userId);
    const triggerItem = makeItem(trigger);
    if (senderName) triggerItem.senderName = senderName;
    const context = [triggerItem, ...selected.slice(RECENT_LIMIT).map((record) =>
      limitText(makeItem(record), OLDER_TEXT_LIMIT))];

    const truncatedReasons = [];
    if (history.interrupted) truncatedReasons.push("read_interrupted");
    if (candidates.length >= history.limit) truncatedReasons.push("history_limit");
    const setting = env.RELAY_MAX_PAYLOAD_BYTES;
    const maxBytes = typeof setting === "string" || typeof setting === "number"
      ? Math.min(positiveInteger(setting, DEFAULT_RELAY_BYTES), HARD_MAX_RELAY_BYTES)
      : DEFAULT_RELAY_BYTES;
    const body = relayBody({
      source: "line",
      text: trigger.text,
      timestamp: trigger.timestamp,
      timestampMs: trigger.timestampMs,
      messageId: trigger.messageId,
      webhookEventId: trigger.webhookEventId,
      userId: trigger.userId,
      ...(senderName ? { senderName } : {}),
    }, recent, context, {
      groupId: group.groupId,
      taipeiDate: group.taipeiDate,
      contextStart: `${group.taipeiDate}T00:00:00+08:00`,
    }, truncatedReasons, maxBytes);

    if (body === null) {
      console.warn("Relay payload exceeds hard size limit");
      return;
    }

    const v1 = createHmac("sha256", env.RELAY_SIGNING_SECRET)
      .update(`${t}.${body}`)
      .digest("hex");

    const response = await fetch(env.RELAY_WEBHOOK_URL, {
      method: "POST",
      redirect: "manual",
      headers: {
        "Content-Type": "application/json",
        "X-Relay-Signature": `t=${t},v1=${v1}`,
      },
      body,
    });
    if (!response.ok) console.warn("Relay returned HTTP status", response.status);
    await response.body?.cancel();
  } catch {
    console.warn("Relay delivery failed");
  }
}

async function relayEvents(rawBody, origin, env) {
  let payload;
  try {
    payload = JSON.parse(decoder.decode(rawBody));
  } catch {
    return;
  }

  if (!Array.isArray(payload?.events)) return;

  const groups = new Map();
  for (const event of payload.events) {
    if (event?.type !== "message" || event.source?.type !== "group") continue;
    const { groupId, userId } = event.source;
    const { message, timestamp: timestampMs } = event;
    if (typeof groupId !== "string" || !groupId.trim() ||
        typeof message?.id !== "string" || !message.id.trim() ||
        typeof timestampMs !== "number") continue;

    const taipeiTime = new Date(timestampMs + TAIPEI_OFFSET_MS);
    const timestamp = new Date(timestampMs);
    if (!Number.isFinite(taipeiTime.getTime()) || !Number.isFinite(timestamp.getTime())) continue;
    const taipeiDate = taipeiTime.toISOString().split("T", 1)[0];
    if (taipeiDate.length !== 10) continue;

    const record = {
      messageId: message.id,
      webhookEventId: event.webhookEventId ?? null,
      userId: userId ?? null,
      timestamp: timestamp.toISOString(),
      timestampMs,
      type: message.type,
    };
    if (message.type === "text" && typeof message.text === "string") {
      record.text = message.text;
    } else if (MEDIA_TYPES.has(message.type)) {
      record.fileName = message.fileName ?? null;
      // A single webhook can contain several large media events.
      record.media = await storeMedia(message, groupId, taipeiDate, env);
    } else {
      continue;
    }

    const keyScope = `${sanitizeId(groupId)}:${taipeiDate}:`;
    const timeKey = String(HISTORY_TIME_MAX - Math.max(0, Math.floor(timestampMs)))
      .padStart(HISTORY_TIME_WIDTH, "0");
    try {
      await env.CHAT_HISTORY?.put(`msgr:${keyScope}${timeKey}:${sanitizeId(message.id)}`, JSON.stringify(record), {
        expirationTtl: HISTORY_TTL_SECONDS,
      });
    } catch {
      console.warn("Chat history write failed");
    }

    if (!groups.has(keyScope)) groups.set(keyScope, { groupId, taipeiDate, records: new Map(), triggers: [] });
    const group = groups.get(keyScope);
    group.records.set(record.messageId, record);
    if (record.text?.includes("工程")) group.triggers.push(record);
  }

  const configuredLimit = env.RELAY_HISTORY_LIMIT;
  const limit = typeof configuredLimit === "string" || typeof configuredLimit === "number"
    ? positiveInteger(configuredLimit, HISTORY_LIMIT)
    : HISTORY_LIMIT;
  for (const [keyScope, group] of groups) {
    if (group.triggers.length === 0) continue;
    if (!env.RELAY_SIGNING_SECRET || !env.RELAY_WEBHOOK_URL) {
      console.warn("Relay configuration incomplete");
      return;
    }

    const triggerIds = new Set(group.triggers.map(({ messageId }) => messageId));
    const { records, interrupted } = await readHistory(env.CHAT_HISTORY, keyScope, triggerIds, limit);
    for (const [id, record] of group.records) records.set(id, record);
    const history = {
      records: [...records.values()].sort((a, b) => b.timestampMs - a.timestampMs),
      interrupted,
      limit,
    };
    for (const trigger of group.triggers) {
      await forwardEvent(trigger, group, history, origin, env);
    }
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname.startsWith(MEDIA_PATH)) {
      return downloadMedia(url, env);
    }
    if (request.method !== "POST") {
      return new Response(null, { status: 405, headers: { Allow: "POST" } });
    }

    let rawBody;
    try {
      rawBody = await readBody(request.body, MAX_BODY_BYTES);
    } catch {
      return new Response(null, { status: 400 });
    }
    if (rawBody === null) return new Response(null, { status: 413 });

    if (!hasValidLineSignature(request.headers.get("X-Line-Signature"), rawBody, env.LINE_CHANNEL_SECRET)) {
      return new Response(null, { status: 401 });
    }

    ctx.waitUntil(Promise.resolve().then(() => relayEvents(rawBody, url.origin, env)));
    return new Response(null, { status: 200 });
  },
};
