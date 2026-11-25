import { Buffer } from "node:buffer";
import { createHmac, timingSafeEqual } from "node:crypto";

const MAX_BODY_BYTES = 1024 * 1024;
const MAX_MEDIA_BYTES = 50 * 1024 * 1024;
const MAX_RELAY_BYTES = 512 * 1024;
const MEDIA_TTL_SECONDS = 3600;
const HISTORY_TTL_SECONDS = 172800;
const HISTORY_PAGE_SIZE = 100;
const MAX_HISTORY_PAGES = 20;
const TAIPEI_OFFSET_MS = 8 * 60 * 60 * 1000;
const LINE_SIGNATURE_LENGTH = 44;
const MEDIA_PATH = "/media/";
const MEDIA_TYPES = new Set(["image", "video", "file"]);
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

async function readHistory(kv, prefix) {
  const records = new Map();
  if (!kv) return { records, truncated: false };

  try {
    let cursor;
    for (let page = 0; page < MAX_HISTORY_PAGES; page++) {
      const result = await kv.list({ prefix, cursor, limit: HISTORY_PAGE_SIZE });
      if (result.keys.length > 0) {
        const values = await kv.get(result.keys.map(({ name }) => name), "json");
        for (const record of values.values()) {
          if (record) records.set(record.messageId, record);
        }
      }
      if (result.list_complete) return { records, truncated: false };
      cursor = result.cursor;
    }
  } catch {
    console.warn("Chat history read failed");
  }
  return { records, truncated: true };
}

function contextItem(record, triggerId, origin, exp, secret) {
  const { media, fileName, ...fields } = record;
  const item = { ...fields, isTrigger: record.messageId === triggerId };
  if (media) {
    const { r2Key, ...metadata } = media;
    if (fileName != null) item.fileName = fileName;
    item.media = metadata;
    if (r2Key && secret) {
      const sig = mediaSignature(secret, r2Key, exp);
      item.downloadUrl = `${origin}${MEDIA_PATH}${encodeURIComponent(r2Key)}?exp=${exp}&sig=${sig}`;
    }
  }
  return item;
}

function relayBody(fields, context, truncated, maxBytes) {
  const baseBytes = Buffer.byteLength(JSON.stringify(fields));
  const sizes = context.map((item) => Buffer.byteLength(JSON.stringify(item)) + 1);
  let entryBytes = sizes.reduce((total, size) => total + size, 0);
  let count = context.length;
  const fits = () => {
    const envelopeBytes = Buffer.byteLength(JSON.stringify({ truncated, contextCount: count, context: [] }));
    // Merge the outer JSON objects and count commas only between context entries.
    return baseBytes + envelopeBytes - 1 + entryBytes - Number(count > 0) <= maxBytes;
  };

  let start = 0;
  while (start < context.length && !fits()) {
    const index = start++;
    if (context[index].isTrigger) continue;
    truncated = true;
    count -= 1;
    entryBytes -= sizes[index];
  }

  if (!fits()) return null;
  return JSON.stringify({
    ...fields,
    truncated,
    contextCount: count,
    context: context.filter((item, index) => index >= start || item.isTrigger),
  });
}

async function forwardEvent(trigger, group, history, origin, env) {
  try {
    const t = unixSeconds();
    const exp = t + positiveInteger(env.MEDIA_URL_TTL_SECONDS, MEDIA_TTL_SECONDS);
    const context = [...history.records.values()]
      .sort((a, b) => a.timestampMs - b.timestampMs ||
        (a.messageId === b.messageId ? 0 : a.messageId < b.messageId ? -1 : 1))
      .map((record) => contextItem(record, trigger.messageId, origin, exp, env.RELAY_SIGNING_SECRET));

    const body = relayBody({
      source: "line",
      groupId: group.groupId,
      userId: trigger.userId,
      text: trigger.text,
      timestamp: trigger.timestamp,
      timestampMs: trigger.timestampMs,
      messageId: trigger.messageId,
      webhookEventId: trigger.webhookEventId,
      taipeiDate: group.taipeiDate,
      contextStart: `${group.taipeiDate}T00:00:00+08:00`,
    }, context, history.truncated, positiveInteger(env.RELAY_MAX_PAYLOAD_BYTES, MAX_RELAY_BYTES));

    if (body === null) {
      console.warn("Relay payload exceeds size limit");
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

    const prefix = `msg:${sanitizeId(groupId)}:${taipeiDate}:`;
    const timeKey = String(Math.max(0, Math.floor(timestampMs))).padStart(15, "0");
    try {
      await env.CHAT_HISTORY?.put(`${prefix}${timeKey}:${sanitizeId(message.id)}`, JSON.stringify(record), {
        expirationTtl: HISTORY_TTL_SECONDS,
      });
    } catch {
      console.warn("Chat history write failed");
    }

    if (!groups.has(prefix)) groups.set(prefix, { groupId, taipeiDate, records: new Map(), triggers: [] });
    const group = groups.get(prefix);
    group.records.set(record.messageId, record);
    if (record.text?.includes("工程")) group.triggers.push(record);
  }

  for (const [prefix, group] of groups) {
    if (group.triggers.length === 0) continue;
    if (!env.RELAY_SIGNING_SECRET || !env.RELAY_WEBHOOK_URL) {
      console.warn("Relay configuration incomplete");
      return;
    }

    const history = await readHistory(env.CHAT_HISTORY, prefix);
    for (const [id, record] of group.records) history.records.set(id, record);
    for (const trigger of group.triggers) {
      history.records.set(trigger.messageId, trigger);
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
