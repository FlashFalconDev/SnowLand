import assert from "node:assert/strict";
import { Buffer } from "node:buffer";
import { randomBytes, webcrypto } from "node:crypto";
import test from "node:test";
import worker from "./worker.js";

const env = {
  LINE_CHANNEL_SECRET: randomBytes(32).toString("hex"),
  RELAY_SIGNING_SECRET: randomBytes(32).toString("hex"),
  RELAY_WEBHOOK_URL: "https://relay.example.invalid/webhook",
};
const event = {
  type: "message",
  source: { type: "group", groupId: "group-test", userId: "user-test" },
  message: { type: "text", id: "message-test", text: "工程進度更新\n已完成 ⛷️" },
  timestamp: Date.parse("2026-01-02T03:04:05.678Z"),
  webhookEventId: "event-test",
};
const BODY_LIMIT = 1024 * 1024;

const WORKER_ORIGIN = "https://worker.example.invalid";
const LINE_CONTENT_ROOT = "https://api-data.line.me/v2/bot/message/";
const LINE_PROFILE_ROOT = "https://api.line.me/v2/bot/group/";
const DAY = "2026-11-25";

function memoryKV(t, { pageSize = 100, eventual = false } = {}) {
  const values = new Map();
  let visible = eventual ? new Map() : values;
  return {
    values,
    publish() {
      visible = new Map(values);
    },
    put: t.mock.fn(async (key, value, { expirationTtl }) => {
      assert.equal(expirationTtl, key.startsWith("profile:") ? 86400 : 172800);
      values.set(key, value);
    }),
    list: t.mock.fn(async ({ prefix, cursor, limit }) => {
      const matching = [...visible.keys()].filter((key) => key.startsWith(prefix)).sort();
      const start = Number(cursor ?? 0);
      const end = start + Math.min(limit, pageSize);
      return {
        keys: matching.slice(start, end).map((name) => ({ name })),
        list_complete: end >= matching.length,
        cursor: end < matching.length ? String(end) : undefined,
      };
    }),
    get: t.mock.fn(async (keys, type) => {
      if (typeof keys === "string") {
        assert.ok(keys.startsWith("profile:"));
        assert.equal(type, "text");
        return visible.get(keys) ?? null;
      }
      assert.equal(type, "json");
      assert.ok(Array.isArray(keys) && keys.length <= 100);
      return new Map(keys.map((key) => [key, JSON.parse(visible.get(key) ?? "null")]));
    }),
  };
}

function memoryR2(t) {
  const objects = new Map();
  return {
    objects,
    put: t.mock.fn(async (key, bytes, { httpMetadata, customMetadata }) => {
      objects.set(key, { bytes: Buffer.from(bytes), httpMetadata, customMetadata });
    }),
    get: t.mock.fn(async (key) => {
      const object = objects.get(key);
      return object ? { ...object, body: new Response(object.bytes).body } : null;
    }),
  };
}

function groupMessage(id, at, message, groupId = event.source.groupId) {
  return {
    type: "message",
    source: { ...event.source, groupId },
    message: { type: "text", ...message, id },
    timestamp: Date.parse(at),
    webhookEventId: `event-${id}`,
  };
}

function savedMessages(kv) {
  return [...kv.values].filter(([key]) => /^(msgr|msg):/.test(key)).map(([, value]) => JSON.parse(value));
}

function listedPages(kv, format) {
  return kv.list.mock.calls.map(({ arguments: [options] }) => options)
    .filter(({ prefix }) => prefix.startsWith(`${format}:`));
}

function moveToLegacyHistory(kv) {
  for (const [key, value] of [...kv.values]) {
    if (!key.startsWith("msgr:")) continue;
    const [, group, date, , id] = key.split(":");
    const time = String(JSON.parse(value).timestampMs).padStart(15, "0");
    kv.values.set(`msg:${group}:${date}:${time}:${id}`, value);
    kv.values.delete(key);
  }
}

function callsTo(fetch, url) {
  return fetch.mock.calls.filter(({ arguments: [target] }) => target === url);
}

async function receive(events, bindings, ctx) {
  const response = await worker.fetch(await signedPost(events), bindings, ctx);
  assert.equal(response.status, 200);
  await finishBackgroundWork(ctx);
}

function relayRequest(fetch) {
  const calls = callsTo(fetch, env.RELAY_WEBHOOK_URL);
  assert.equal(calls.length, 1);
  return calls[0].arguments[1];
}

function relayPayload(fetch) {
  return JSON.parse(relayRequest(fetch).body);
}


async function sign(secret, bytes, encoding) {
  const key = await webcrypto.subtle.importKey(
    "raw",
    Buffer.from(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await webcrypto.subtle.sign("HMAC", key, Buffer.from(bytes));
  return Buffer.from(digest).toString(encoding);
}

function lineSignature(body) {
  return sign(env.LINE_CHANNEL_SECRET, body, "base64");
}

function post(body, signature) {
  const headers = new Headers();
  if (signature !== undefined) headers.set("X-Line-Signature", signature);
  return new Request("https://worker.example.invalid/", { method: "POST", headers, body });
}

async function signedPost(events) {
  const body = JSON.stringify({ events });
  return post(body, await lineSignature(body));
}

function mockRelay(t, respond = async () => new Response(null, { status: 204 })) {
  return mockFetch(t, async (url, request) => {
    assert.equal(url, env.RELAY_WEBHOOK_URL);
    return respond(url, request);
  });
}

function mockFetch(t, respond) {
  const fetch = t.mock.method(globalThis, "fetch", respond);
  const ctx = { waitUntil: t.mock.fn() };
  return { fetch, ctx };
}

async function finishBackgroundWork(ctx) {
  await Promise.all(ctx.waitUntil.mock.calls.map(({ arguments: [promise] }) => promise));
}

function assertNoRelay(fetch, ctx) {
  assert.equal(fetch.mock.callCount(), 0);
  assert.equal(ctx.waitUntil.mock.callCount(), 0);
}

test("acknowledges signed raw bytes while the relay is pending and signs the exact outbound body", { timeout: 2000 }, async (t) => {
  const signingTime = Date.parse("2026-01-02T03:04:06.987Z");
  t.mock.method(Date, "now", () => signingTime);

  let completeDelivery;
  let startDelivery;
  const delivery = new Promise((resolve) => { completeDelivery = resolve; });
  const started = new Promise((resolve) => { startDelivery = resolve; });
  const { fetch, ctx } = mockRelay(t, () => {
    startDelivery();
    return delivery;
  });
  const kv = memoryKV(t);
  const rawBody = `{\r\n  "events": [ ${JSON.stringify(event)} ]\r\n}\n`;

  try {
    const response = await worker.fetch(post(rawBody, await lineSignature(rawBody)), { ...env, CHAT_HISTORY: kv }, ctx);
    assert.equal(response.status, 200);
    assert.equal(ctx.waitUntil.mock.callCount(), 1);
    await started;
    assert.equal(fetch.mock.callCount(), 1);

    const [url, request] = fetch.mock.calls[0].arguments;
    assert.equal(url, env.RELAY_WEBHOOK_URL);
    assert.equal(request.method, "POST");
    assert.equal(request.redirect, "manual");
    const headers = new Headers(request.headers);
    assert.equal(headers.get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(request.body), {
      summary: "觸發前最新 0 則見 recent；較舊 0 則在 context",
      source: "line",
      groupId: event.source.groupId,
      userId: event.source.userId,
      text: event.message.text,
      timestamp: "2026-01-02T03:04:05.678Z",
      timestampMs: event.timestamp,
      messageId: event.message.id,
      webhookEventId: event.webhookEventId,
      taipeiDate: "2026-01-02",
      contextStart: "2026-01-02T00:00:00+08:00",
      recent: [],
      recentCount: 0,
      truncated: false,
      contextCount: 1,
      context: [{
        messageId: event.message.id,
        webhookEventId: event.webhookEventId,
        userId: event.source.userId,
        timestamp: "2026-01-02T03:04:05.678Z",
        timestampMs: event.timestamp,
        type: "text",
        text: event.message.text,
        taipeiTime: "2026-01-02 11:04:05",
        isTrigger: true,
      }],
    });

    const match = /^t=(\d+),v1=([0-9a-f]{64})$/.exec(headers.get("X-Relay-Signature"));
    assert.ok(match);
    const [, timestamp, signature] = match;
    assert.equal(Number(timestamp), Math.floor(signingTime / 1000));
    assert.equal(signature, await sign(env.RELAY_SIGNING_SECRET, `${timestamp}.${request.body}`, "hex"));
  } finally {
    completeDelivery(new Response(null, { status: 204 }));
    await finishBackgroundWork(ctx);
  }
});

test("rejects a matching-length signature for different raw bytes", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const body = JSON.stringify({ events: [event] });
  const kv = memoryKV(t);
  const response = await worker.fetch(post(`${body}\n`, await lineSignature(body)), { ...env, CHAT_HISTORY: kv }, ctx);
  assert.equal(kv.put.mock.callCount(), 0);
  assert.equal(response.status, 401);
  assertNoRelay(fetch, ctx);
});

test("rejects a malformed signature without throwing", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const response = await worker.fetch(post("{}", "not-base64"), env, ctx);
  assert.equal(response.status, 401);
  assertNoRelay(fetch, ctx);
});

test("rejects a missing signature", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const kv = memoryKV(t);
  const response = await worker.fetch(post(JSON.stringify({ events: [event] })), { ...env, CHAT_HISTORY: kv }, ctx);
  assert.equal(kv.put.mock.callCount(), 0);
  assert.equal(response.status, 401);
  assertNoRelay(fetch, ctx);
});

test("rejects a signed request when the LINE secret binding is missing", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const response = await worker.fetch(await signedPost([event]), {}, ctx);
  assert.equal(response.status, 401);
  assertNoRelay(fetch, ctx);
});

for (const [description, ignoredEvent] of [
  ["non-group", { ...event, source: { type: "user" } }],
  ["non-text", { ...event, message: { ...event.message, type: "image" } }],
  ["missing keyword", { ...event, message: { ...event.message, text: "目前進度" } }],
  ["non-message", { ...event, type: "follow" }],
]) {
  test(`acknowledges and ignores a ${description} event`, async (t) => {
    const { fetch, ctx } = mockRelay(t);
    const response = await worker.fetch(await signedPost([ignoredEvent]), env, ctx);
    assert.equal(response.status, 200);
    await finishBackgroundWork(ctx);
    assert.equal(fetch.mock.callCount(), 0);
  });
}

test("rejects non-POST requests", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  for (const [path, method] of [["/", "GET"], ["/other", "GET"], ["/media/key", "HEAD"], ["/media/key", "PUT"]]) {
    const response = await worker.fetch(new Request(`${WORKER_ORIGIN}${path}`, { method }), env, ctx);
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("Allow"), "POST");
  }
  assertNoRelay(fetch, ctx);
});

test("acknowledges an empty LINE verification request", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const response = await worker.fetch(await signedPost([]), env, ctx);
  assert.equal(response.status, 200);
  await finishBackgroundWork(ctx);
  assert.equal(fetch.mock.callCount(), 0);
});

test("acknowledges a signed invalid JSON body without forwarding", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const body = "{";
  const response = await worker.fetch(post(body, await lineSignature(body)), env, ctx);
  assert.equal(response.status, 200);
  await finishBackgroundWork(ctx);
  assert.equal(fetch.mock.callCount(), 0);
});

test("accepts a signed request with exactly 1 MiB of body bytes", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const body = '{"events":[]}'.padEnd(BODY_LIMIT);
  const response = await worker.fetch(post(body, await lineSignature(body)), env, ctx);
  assert.equal(response.status, 200);
  await finishBackgroundWork(ctx);
  assert.equal(fetch.mock.callCount(), 0);
});

test("cancels an oversized stream even when Content-Length understates the size", { timeout: 2000 }, async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const body = Buffer.from('{"events":[]}'.padEnd(BODY_LIMIT + 1));
  const cancel = t.mock.fn();
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(body.subarray(0, BODY_LIMIT));
      controller.enqueue(body.subarray(BODY_LIMIT));
    },
    cancel,
  });
  const request = new Request("https://worker.example.invalid/", {
    method: "POST",
    headers: { "Content-Length": "1", "X-Line-Signature": await lineSignature(body) },
    body: stream,
    duplex: "half",
  });

  const response = await worker.fetch(request, env, ctx);
  assert.equal(response.status, 413);
  assert.equal(cancel.mock.callCount(), 1);
  assertNoRelay(fetch, ctx);
});

test("forwards each matching event once and preserves a missing userId as null", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const response = await worker.fetch(await signedPost([
    event,
    { ...event, type: "follow" },
    {
      ...event,
      source: { type: "group", groupId: event.source.groupId },
      message: { ...event.message, id: "message-second" },
      webhookEventId: "event-second",
    },
  ]), env, ctx);
  assert.equal(response.status, 200);
  await finishBackgroundWork(ctx);
  const bodies = fetch.mock.calls.map(({ arguments: [, request] }) => JSON.parse(request.body));
  assert.deepEqual(bodies.map(({ webhookEventId }) => webhookEventId), ["event-test", "event-second"]);
  assert.deepEqual(bodies.map(({ userId }) => userId), [event.source.userId, null]);
});

test("isolates relay failures and logs only the failure status", async (t) => {
  const warn = t.mock.method(console, "warn", () => {});
  const { fetch, ctx } = mockRelay(t, async (_url, request) => {
    if (JSON.parse(request.body).webhookEventId === event.webhookEventId) {
      throw new Error(event.message.text);
    }
    return new Response(null, { status: 503 });
  });

  const response = await worker.fetch(await signedPost([
    event,
    { ...event, webhookEventId: "event-second" },
  ]), env, ctx);
  assert.equal(response.status, 200);
  await finishBackgroundWork(ctx);
  assert.equal(fetch.mock.callCount(), 2);
  assert.deepEqual(warn.mock.calls.map(({ arguments: args }) => args), [
    ["Relay delivery failed"],
    ["Relay returned HTTP status", 503],
  ]);
});

test("saves ordinary text verbatim in KV for 48 hours without contacting the routine", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const kv = memoryKV(t);
  const note = groupMessage("msg/1..", `${DAY}T01:02:03.004Z`, {
    text: "進度已更新\n  https://example.invalid/path?a=1&b=2  ",
  }, "group/..甲");
  const invalidEvents = [
    { ...note, source: { type: "user", userId: "user-test" } },
    { ...note, source: { type: "group", groupId: "" } },
    { ...note, message: { ...note.message, id: "" } },
    { ...note, timestamp: String(note.timestamp) },
    { ...note, message: { type: "sticker", id: "ignored" } },
  ];

  await receive([note, ...invalidEvents], { ...env, CHAT_HISTORY: kv }, ctx);
  assert.equal(fetch.mock.callCount(), 0);
  assert.equal(kv.list.mock.callCount(), 0);
  assert.equal(kv.put.mock.callCount(), 1);
  const reversedTime = String(999_999_999_999_999 - note.timestamp).padStart(15, "0");
  const key = `msgr:group____:${DAY}:${reversedTime}:msg_1__`;
  assert.deepEqual(JSON.parse(kv.values.get(key)), {
    messageId: note.message.id,
    webhookEventId: note.webhookEventId,
    userId: note.source.userId,
    timestamp: `${DAY}T01:02:03.004Z`,
    timestampMs: note.timestamp,
    type: "text",
    text: note.message.text,
  });
});

test("stores private media and relays prioritized same-day history across KV pages and an unseen batch", async (t) => {
  const kv = memoryKV(t, { pageSize: 2, eventual: true });
  const r2 = memoryR2(t);
  const token = randomBytes(32).toString("hex");
  const bindings = { ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: r2, LINE_CHANNEL_ACCESS_TOKEN: token };
  const clock = Date.parse(`${DAY}T12:00:00Z`);
  t.mock.method(Date, "now", () => clock);

  const previousDay = groupMessage("previous", "2026-11-24T15:59:00Z", { text: "跨日以前" });
  const note = groupMessage("a-note", "2026-11-24T16:00:00Z", { text: "留原文" });
  const link = groupMessage("b-link", `${DAY}T01:00:00Z`, { text: "連結 https://example.invalid/doc?x=1" });
  const image = groupMessage("photo/1", `${DAY}T01:00:00Z`, { type: "image" });
  const video = groupMessage("video-2", `${DAY}T03:00:00Z`, { type: "video", duration: 6200 });
  const file = groupMessage("file-3", `${DAY}T04:00:00Z`, { type: "file", fileName: "交付.pdf" });
  const trigger = groupMessage("trigger", `${DAY}T05:00:00Z`, { text: "工程進度更新 ⛷️" });
  const otherGroup = groupMessage("other", `${DAY}T02:00:00Z`, { text: "其他群組" }, "group-other");
  const attachments = [
    [image, Buffer.from([0x89, 0x50, 0x4e, 0x47]), "image/png", "photo_1"],
    [video, Buffer.from("mp4 data"), "video/mp4", "video-2"],
    [file, Buffer.from("%PDF data"), "application/pdf", "file-3"],
  ];
  const contentUrl = (id) => `${LINE_CONTENT_ROOT}${encodeURIComponent(id)}/content`;
  const byUrl = new Map(attachments.map(([{ message }, bytes, contentType]) => [
    contentUrl(message.id), { bytes, contentType },
  ]));
  const { fetch, ctx } = mockFetch(t, async (url, request) => {
    if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
    if (url.startsWith(LINE_PROFILE_ROOT)) return new Response(null, { status: 404 });
    const { bytes, contentType } = byUrl.get(url);
    assert.equal(request.method, "GET");
    assert.equal(request.redirect, "manual");
    assert.equal(new Headers(request.headers).get("Authorization"), `Bearer ${token}`);
    return new Response(bytes, { headers: { "Content-Type": contentType, "Content-Length": String(bytes.length) } });
  });

  await receive([previousDay, image, link, note, otherGroup], bindings, ctx);
  assert.equal(callsTo(fetch, env.RELAY_WEBHOOK_URL).length, 0);
  kv.publish();

  const updatedNote = { ...note, message: { ...note.message, text: "同一則更新的原文" } };
  await receive([trigger, file, video, updatedNote], bindings, ctx);
  const payload = relayPayload(fetch);
  assert.equal(payload.taipeiDate, DAY);
  assert.equal(payload.contextStart, `${DAY}T00:00:00+08:00`);
  assert.equal(payload.truncated, false);
  assert.equal(payload.contextCount, 6);
  assert.deepEqual(payload.recent.map(({ messageId, isTrigger }) => [messageId, isTrigger]),
    [file, video, link, image, note].map(({ message }) => [message.id, false]));
  assert.deepEqual(payload.context.map(({ messageId, isTrigger }) => [messageId, isTrigger]), [[trigger.message.id, true]]);
  assert.equal(payload.recent[4].text, updatedNote.message.text);
  assert.equal(payload.recent[2].text, link.message.text);
  const newestPages = listedPages(kv, "msgr");
  assert.equal(newestPages.length, 2);
  assert.deepEqual(newestPages.map(({ cursor }) => cursor), [undefined, "2"]);
  assert.equal(r2.put.mock.callCount(), 3);
  assert.equal(fetch.mock.callCount(), 5);

  for (const [attachment, bytes, contentType, keyId] of attachments) {
    const { message } = attachment;
    const key = `line-media/${DAY}/${attachment.source.groupId}/${keyId}`;
    assert.equal(callsTo(fetch, contentUrl(message.id)).length, 1);
    assert.deepEqual(r2.objects.get(key), {
      bytes,
      httpMetadata: { contentType },
      customMetadata: { messageId: message.id, mediaType: message.type, taipeiDate: DAY },
    });
    const metadata = { type: message.type, contentType, size: bytes.length, duration: message.duration ?? null, status: "stored" };
    const saved = savedMessages(kv).find(({ messageId }) => messageId === message.id);
    assert.deepEqual(saved.media, { ...metadata, r2Key: key });
    assert.equal(saved.fileName, message.fileName ?? null);

    const item = payload.recent.find(({ messageId }) => messageId === message.id);
    assert.deepEqual(item.media, metadata);
    assert.equal(item.fileName, message.fileName);
    const exp = Math.floor(clock / 1000) + 3600;
    const sig = await sign(env.RELAY_SIGNING_SECRET, `media\n${key}\n${exp}`, "hex");
    assert.equal(item.downloadUrl, `${WORKER_ORIGIN}/media/${encodeURIComponent(key)}?exp=${exp}&sig=${sig}`);
    const response = await worker.fetch(new Request(item.downloadUrl), bindings, ctx);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("Content-Type"), contentType);
    assert.equal(response.headers.get("Cache-Control"), "private, no-store");
    assert.equal(response.headers.get("X-Content-Type-Options"), "nosniff");
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), bytes);
  }

  const [, sent] = callsTo(fetch, env.RELAY_WEBHOOK_URL)[0].arguments;
  const [, tValue, signature] = /^t=(\d+),v1=([0-9a-f]{64})$/.exec(sent.headers["X-Relay-Signature"]);
  assert.equal(signature, await sign(env.RELAY_SIGNING_SECRET, `${tValue}.${sent.body}`, "hex"));
});

test("isolates context at midnight in Taipei even within one webhook", async (t) => {
  const kv = memoryKV(t);
  const { fetch, ctx } = mockRelay(t);
  const yesterday = groupMessage("late", "2026-11-24T15:59:00Z", { text: "昨晚 23:59" });
  const midnight = groupMessage("midnight", "2026-11-24T16:00:00Z", { text: "今天 00:00" });
  const trigger = groupMessage("early", "2026-11-24T16:01:00Z", { text: "工程 00:01" });

  await receive([yesterday, trigger, midnight], { ...env, CHAT_HISTORY: kv }, ctx);
  const payload = relayPayload(fetch);
  assert.equal(payload.taipeiDate, DAY);
  assert.equal(payload.contextStart, `${DAY}T00:00:00+08:00`);
  assert.deepEqual(payload.recent.map(({ messageId }) => messageId), ["midnight"]);
  assert.deepEqual(payload.context.map(({ messageId }) => messageId), ["early"]);
});

test("rejects unsigned, expired, altered or malformed media requests before accessing R2", async (t) => {
  const kv = memoryKV(t);
  const r2 = memoryR2(t);
  const bindings = { ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: r2 };
  const { fetch, ctx } = mockRelay(t);
  const exp = 1800000000;
  t.mock.method(Date, "now", () => exp * 1000);
  const key = "line-media/2026-11-25/group-test/image-1";
  const sig = await sign(env.RELAY_SIGNING_SECRET, `media\n${key}\n${exp}`, "hex");
  const oldSig = await sign(env.RELAY_SIGNING_SECRET, `media\n${key}\n${exp - 1}`, "hex");
  const address = `${WORKER_ORIGIN}/media/${encodeURIComponent(key)}`;
  const invalid = [
    [`${WORKER_ORIGIN}/media/%XY`, 400],
    [`${WORKER_ORIGIN}/media/${encodeURIComponent("other/prefix")}`, 400],
    [`${WORKER_ORIGIN}/media/${encodeURIComponent("line-media/dir/../image")}`, 400],
    [`${WORKER_ORIGIN}/media/${encodeURIComponent("line-media/a\\b")}`, 400],
    [`${address}?exp=${exp}`, 403],
    [`${address}?sig=${sig}`, 403],
    [`${address}?exp=${exp - 1}&sig=${oldSig}`, 403],
    [`${address}?exp=${exp}.5&sig=${sig}`, 403],
    [`${address}?exp=${exp}%0A&sig=${sig}`, 403],
    [`${address}?exp=${exp}&sig=${sig[0] === "0" ? "1" : "0"}${sig.slice(1)}`, 403],
    [`${address}?exp=${exp}&sig=A${sig.slice(1)}`, 403],
  ];
  for (const [url, status] of invalid) {
    const response = await worker.fetch(new Request(url), bindings, ctx);
    assert.equal(response.status, status);
  }
  assert.equal(r2.get.mock.callCount(), 0);
  assert.equal(kv.put.mock.callCount(), 0);
  assertNoRelay(fetch, ctx);

  const valid = new Request(`${address}?exp=${exp}&sig=${sig}`);
  assert.equal((await worker.fetch(valid, bindings, ctx)).status, 404);
  assert.equal(r2.get.mock.callCount(), 1);
  assert.equal((await worker.fetch(valid, env, ctx)).status, 503);
  assert.equal((await worker.fetch(valid, { MEDIA_BUCKET: r2 }, ctx)).status, 503);
});

for (const [fileType, declaredBytes] of [["video", 11], ["file", 1]]) {
  test(`cancels a ${fileType} over the media size limit without writing to R2`, async (t) => {
    const kv = memoryKV(t);
    const r2 = memoryR2(t);
    const cancel = t.mock.fn();
    const content = new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array(6));
        controller.enqueue(new Uint8Array(5));
      },
      cancel,
    });
    const media = groupMessage("large-media", `${DAY}T02:00:00Z`, { type: fileType });
    const { fetch, ctx } = mockFetch(t, async (url) => {
      assert.equal(url, `${LINE_CONTENT_ROOT}large-media/content`);
      return new Response(content, { headers: { "Content-Length": String(declaredBytes) } });
    });

    await receive([media], {
      ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: r2, MEDIA_MAX_BYTES: "10",
      LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex"),
    }, ctx);
    assert.equal(cancel.mock.callCount(), 1);
    assert.equal(fetch.mock.callCount(), 1);
    assert.equal(r2.put.mock.callCount(), 0);
    const [record] = savedMessages(kv);
    assert.equal(record.media.status, "skipped_too_large");
    assert.equal(record.media.r2Key, null);
  });
}

test("returns 200 before a media write finishes", { timeout: 2000 }, async (t) => {
  const kv = memoryKV(t);
  const r2 = memoryR2(t);
  let releaseWrite;
  const pending = new Promise((resolve) => { releaseWrite = resolve; });
  t.mock.method(r2, "put", () => pending);
  const image = groupMessage("pending-image", `${DAY}T04:00:00Z`, { type: "image" });
  const { ctx } = mockFetch(t, async (url) => {
    assert.equal(url, `${LINE_CONTENT_ROOT}pending-image/content`);
    return new Response("image");
  });

  try {
    const response = await worker.fetch(await signedPost([image]), {
      ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: r2, LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex"),
    }, ctx);
    assert.equal(response.status, 200);
    assert.equal(ctx.waitUntil.mock.callCount(), 1);
    assert.equal(kv.put.mock.callCount(), 0);
  } finally {
    releaseWrite();
    await finishBackgroundWork(ctx);
  }
  assert.equal(savedMessages(kv)[0].media.status, "stored");
});

test("records a missing LINE token without downloading or issuing a link", async (t) => {
  const kv = memoryKV(t);
  const r2 = memoryR2(t);
  const { fetch, ctx } = mockRelay(t);
  const bindings = { ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: r2 };
  const noToken = groupMessage("no-token", `${DAY}T04:00:00Z`, { type: "image" });
  const trigger = groupMessage("trigger", `${DAY}T04:00:02Z`, { text: "工程" });

  await receive([noToken], bindings, ctx);
  assert.equal(fetch.mock.callCount(), 0);
  assert.equal(r2.put.mock.callCount(), 0);
  assert.equal(savedMessages(kv)[0].media.status, "skipped_missing_token");

  await receive([trigger], bindings, ctx);
  const [item] = relayPayload(fetch).recent;
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(item.media.status, "skipped_missing_token");
  assert.equal(Object.hasOwn(item, "downloadUrl"), false);
  assert.equal(Object.hasOwn(item.media, "r2Key"), false);
});

test("relays same-day text and links with media metadata when R2 is unbound", async (t) => {
  const kv = memoryKV(t);
  const { fetch, ctx } = mockFetch(t, async (url) => {
    if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
    assert.ok(url.startsWith(LINE_PROFILE_ROOT));
    return new Response(null, { status: 404 });
  });
  const bindings = { ...env, CHAT_HISTORY: kv, LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex") };
  const yesterday = groupMessage("yesterday", "2026-11-24T15:59:59.999Z", { text: "昨天" });
  const note = groupMessage("note", "2026-11-24T16:00:00Z", { text: "台北午夜的更新" });
  const link = groupMessage("link", `${DAY}T01:00:00Z`, {
    text: "參考連結\n  https://example.invalid/doc?x=%E6%96%87&y=2#part  ",
  });
  const image = groupMessage("image", `${DAY}T02:00:00Z`, { type: "image" });
  const video = groupMessage("video", `${DAY}T03:00:00Z`, { type: "video", duration: 6200 });
  const file = groupMessage("file", `${DAY}T04:00:00Z`, { type: "file", fileName: "交付.pdf" });
  const trigger = groupMessage("trigger", `${DAY}T05:00:00Z`, { text: "工程更新" });

  await receive([yesterday, note, link, image, video, file], bindings, ctx);
  assert.equal(fetch.mock.callCount(), 0);
  assert.equal(kv.put.mock.callCount(), 6);
  const saved = savedMessages(kv);
  assert.equal(saved[1].text, note.message.text);
  assert.equal(saved[2].text, link.message.text);

  await receive([trigger], bindings, ctx);
  assert.equal(fetch.mock.callCount(), 2);
  assert.equal(savedMessages(kv).at(-1).text, trigger.message.text);
  const payload = relayPayload(fetch);
  assert.equal(payload.contextStart, `${DAY}T00:00:00+08:00`);
  assert.equal(payload.truncated, false);
  assert.equal(payload.contextCount, 6);
  assert.equal(payload.text, trigger.message.text);
  assert.deepEqual(payload.recent.map(({ messageId, isTrigger }) => [messageId, isTrigger]), [
    ["file", false], ["video", false], ["image", false], ["link", false], ["note", false],
  ]);
  assert.deepEqual(payload.context.map(({ messageId, isTrigger, text }) => [messageId, isTrigger, text]), [
    ["trigger", true, trigger.message.text],
  ]);
  assert.deepEqual(payload.recent.filter(({ type }) => type === "text").map(({ text }) => text),
    [link.message.text, note.message.text]);

  for (const { message } of [image, video, file]) {
    const metadata = {
      type: message.type, contentType: null, size: null, duration: message.duration ?? null, status: "skipped_no_bucket",
    };
    const record = saved.find(({ messageId }) => messageId === message.id);
    const item = payload.recent.find(({ messageId }) => messageId === message.id);
    assert.deepEqual(record.media, { ...metadata, r2Key: null });
    assert.equal(record.fileName, message.fileName ?? null);
    assert.deepEqual(item.media, metadata);
    assert.equal(item.fileName, message.fileName);
    assert.equal(Object.hasOwn(item, "downloadUrl"), false);
  }
});

test("withholds a saved media link when R2 is no longer bound", async (t) => {
  const kv = memoryKV(t);
  const r2 = memoryR2(t);
  const { fetch, ctx } = mockFetch(t, async (url) => {
    if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
    if (url.startsWith(LINE_PROFILE_ROOT)) return new Response(null, { status: 404 });
    assert.equal(url, `${LINE_CONTENT_ROOT}stored-image/content`);
    return new Response("image", { headers: { "Content-Type": "image/png" } });
  });
  const bindings = { ...env, CHAT_HISTORY: kv, LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex") };
  const image = groupMessage("stored-image", `${DAY}T04:00:00Z`, { type: "image" });
  const trigger = groupMessage("trigger", `${DAY}T04:00:01Z`, { text: "工程" });

  await receive([image], { ...bindings, MEDIA_BUCKET: r2 }, ctx);
  assert.equal(fetch.mock.callCount(), 1);
  fetch.mock.resetCalls();
  const [saved] = savedMessages(kv);
  assert.equal(saved.media.status, "stored");

  await receive([trigger], bindings, ctx);
  assert.equal(fetch.mock.callCount(), 2);
  const [item] = relayPayload(fetch).recent;
  assert.equal(item.messageId, image.message.id);
  assert.deepEqual(item.media, {
    type: "image", contentType: "image/png", size: 5, duration: null, status: "skipped_no_bucket",
  });
  assert.equal(Object.hasOwn(item, "downloadUrl"), false);
  assert.deepEqual(savedMessages(kv)[0], saved);
});

test("enforces the UTF-8 payload limit while keeping the trigger and newest context", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const oldest = groupMessage("oldest", `${DAY}T01:00:00Z`, { text: "舊".repeat(160) });
  const recent = Array.from({ length: 10 }, (_, i) => ({
    ...groupMessage(`newest-${i}`, `${DAY}T02:00:00Z`, { text: "新".repeat(8) }),
    timestamp: Date.parse(`${DAY}T02:00:00Z`) + i,
  }));
  const trigger = groupMessage("trigger", `${DAY}T03:00:00Z`, { text: "工程原因 ⛷️" });
  const batch = [oldest, ...recent, trigger];

  await receive(batch, env, ctx);
  const [, full] = fetch.mock.calls[0].arguments;
  const limit = full.body.length;
  assert.ok(Buffer.byteLength(full.body) > limit);
  fetch.mock.resetCalls();

  await receive(batch, { ...env, RELAY_MAX_PAYLOAD_BYTES: String(limit) }, ctx);
  const payload = relayPayload(fetch);
  assert.equal(payload.truncated, true);
  assert.equal(payload.contextCount, 11);
  assert.ok(Buffer.byteLength(relayRequest(fetch).body) <= limit);
  assert.deepEqual(payload.truncatedReasons, ["payload_limit"]);
  assert.deepEqual(payload.context.map(({ messageId, isTrigger }) => [messageId, isTrigger]), [["trigger", true]]);
  assert.deepEqual(payload.recent.map(({ messageId, isTrigger }) => [messageId, isTrigger]),
    recent.toReversed().map(({ message }) => [message.id, false]));
});

test("skips an outbound payload when the trigger alone exceeds the hard limit", async (t) => {
  const warn = t.mock.method(console, "warn", () => {});
  const kv = memoryKV(t);
  const { fetch, ctx } = mockRelay(t);
  const trigger = { ...event, message: { ...event.message, text: "工程" + "測".repeat(90_000) } };
  await receive([trigger], { ...env, CHAT_HISTORY: kv, RELAY_MAX_PAYLOAD_BYTES: "1048576" }, ctx);
  assert.equal(savedMessages(kv).length, 1);
  assert.equal(fetch.mock.callCount(), 0);
  assert.deepEqual(warn.mock.calls.map(({ arguments: args }) => args), [["Relay payload exceeds hard size limit"]]);
});

test("marks partial history at the page cap and still includes the current trigger", async (t) => {
  const kv = memoryKV(t, { pageSize: 1, eventual: true });
  const { fetch, ctx } = mockRelay(t);
  const notes = Array.from({ length: 21 }, (_, i) =>
    groupMessage(`note-${i}`, `${DAY}T01:${String(i).padStart(2, "0")}:00Z`, { text: "待處理" }));
  const bindings = { ...env, CHAT_HISTORY: kv };
  await receive(notes, bindings, ctx);
  kv.publish();

  const trigger = groupMessage("trigger", `${DAY}T02:00:00Z`, { text: "工程" });
  await receive([trigger], bindings, ctx);
  const payload = relayPayload(fetch);
  assert.equal(listedPages(kv, "msgr").length, 20);
  assert.equal(payload.contextCount, 21);
  assert.equal(payload.context[0].messageId, trigger.message.id);
  assert.equal(payload.truncated, true);
});

for (const failure of ["later page error", "page cap"]) {
  test(`keeps messages from separate evening posts when legacy history hits a ${failure}`, async (t) => {
    const kv = memoryKV(t, { pageSize: 2, eventual: true });
    const bindings = {
      ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: memoryR2(t),
      LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex"),
    };
    const { fetch, ctx } = mockFetch(t, async (url) => {
      if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
      if (url.startsWith(LINE_PROFILE_ROOT)) return new Response(null, { status: 404 });
      assert.ok(url.startsWith(LINE_CONTENT_ROOT));
      return new Response(new Uint8Array([1, 2, 3]), { headers: { "Content-Type": "image/png" } });
    });
    const warn = t.mock.method(console, "warn", () => {});
    const morning = Array.from({ length: 47 }, (_, i) => ({
      ...groupMessage(`morning-${i}`, `${DAY}T01:00:00Z`, i === 0 ? { type: "image" } : { text: "測試早班" }),
      timestamp: Date.parse(`${DAY}T01:00:00Z`) + i,
    }));
    await receive(morning, bindings, ctx);
    moveToLegacyHistory(kv);

    const evening = [
      groupMessage("evening-image", `${DAY}T13:00:00.000Z`, { type: "image" }),
      groupMessage("evening-a", `${DAY}T13:00:00.001Z`, { text: "測試晚班　樣本甲 👩‍💻" }),
      groupMessage("evening-b", `${DAY}T13:00:00.002Z`, { text: "測試晚班　樣本乙 🧪" }),
    ];
    for (const item of evening) await receive([item], bindings, ctx);
    kv.publish();
    if (failure === "later page error") {
      const list = kv.list;
      kv.list = t.mock.fn(async (options) => {
        if (options.prefix.startsWith("msg:") && options.cursor) throw new Error("test page failure");
        return list(options);
      });
    }

    const trigger = groupMessage("evening-trigger", `${DAY}T13:02:55Z`, { text: "工程測試" });
    await receive([trigger], bindings, ctx);
    const payload = relayPayload(fetch);
    assert.equal(listedPages(kv, "msg").length, failure === "later page error" ? 2 : 20);
    assert.equal(warn.mock.callCount(), failure === "later page error" ? 1 : 0);
    assert.equal(payload.truncated, true);
    assert.deepEqual(payload.truncatedReasons, ["read_interrupted"]);
    assert.equal(payload.contextCount, failure === "later page error" ? 6 : 44);
    const morningImage = [...payload.recent, ...payload.context].find(({ messageId }) => messageId === "morning-0");
    assert.equal(morningImage.media.status, "stored");
    const [noteB, noteA, image] = payload.recent;
    const [first] = payload.context;
    assert.equal(image.messageId, evening[0].message.id);
    assert.equal(image.media.status, "stored");
    assert.equal(typeof image.downloadUrl, "string");
    assert.equal((await worker.fetch(new Request(image.downloadUrl), bindings, ctx)).status, 200);
    assert.deepEqual([noteA.text, noteB.text, first.text], [evening[1].message.text, evening[2].message.text, trigger.message.text]);
    assert.equal(first.messageId, trigger.message.id);
    assert.equal(first.isTrigger, true);
  });
}

test("stops listing after 50 newest non-trigger messages even when KV lists the trigger", async (t) => {
  const kv = memoryKV(t, { pageSize: 26 });
  const { fetch, ctx } = mockRelay(t);
  const bindings = { ...env, CHAT_HISTORY: kv };
  const notes = Array.from({ length: 60 }, (_, i) => ({
    ...groupMessage(`note-${i}`, `${DAY}T01:00:00Z`, { text: "測試歷史" }),
    timestamp: Date.parse(`${DAY}T01:00:00Z`) + i,
  }));
  await receive(notes, bindings, ctx);
  const trigger = groupMessage("trigger", `${DAY}T02:00:00Z`, { text: "工程測試" });
  await receive([trigger], bindings, ctx);

  const payload = relayPayload(fetch);
  assert.equal(payload.contextCount, 51);
  assert.deepEqual([...payload.recent, ...payload.context.slice(1)].map(({ messageId }) => messageId),
    notes.slice(10).reverse().map(({ message }) => message.id));
  assert.equal(payload.context[0].messageId, trigger.message.id);
  assert.equal(payload.context[0].isTrigger, true);
  assert.equal(payload.truncated, true);
  assert.deepEqual(payload.truncatedReasons, ["history_limit"]);
  assert.deepEqual(listedPages(kv, "msgr").map(({ cursor, limit }) => [cursor, limit]), [[undefined, 50], ["26", 25]]);
  assert.deepEqual(kv.get.mock.calls.map(({ arguments: [keys] }) => keys.length), [26, 25]);
});

test("uses the default history limit for invalid settings and marks an exact limit", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const notes = Array.from({ length: 50 }, (_, i) => ({
    ...groupMessage(`note-${i}`, `${DAY}T01:00:00Z`, { text: "測試歷史" }),
    timestamp: Date.parse(`${DAY}T01:00:00Z`) + i,
  }));
  const trigger = groupMessage("trigger", `${DAY}T02:00:00Z`, { text: "工程測試" });
  for (const setting of ["", "0", "-1", "2.5", "invalid", "9007199254740992", true, [2]]) {
    fetch.mock.resetCalls();
    await receive([...notes, trigger], { ...env, RELAY_HISTORY_LIMIT: setting }, ctx);
    const payload = relayPayload(fetch);
    assert.equal(payload.contextCount, 51);
    assert.deepEqual(payload.truncatedReasons, ["history_limit"]);
  }
});

test("counts UTF-8 bytes including all truncation reasons and drops only whole entries", async (t) => {
  const kv = memoryKV(t, { eventual: true });
  kv.list.mock.mockImplementation(async ({ prefix }) => {
    if (prefix.startsWith("msg:")) throw new Error("test list failure");
    return { keys: [], list_complete: true };
  });
  const bindings = {
    ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: memoryR2(t), RELAY_HISTORY_LIMIT: "12",
    LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex"),
  };
  const { fetch, ctx } = mockFetch(t, async (url) => {
    if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
    if (url.startsWith(LINE_PROFILE_ROOT)) return new Response(null, { status: 404 });
    assert.ok(url.startsWith(LINE_CONTENT_ROOT));
    return new Response(new Uint8Array([1]));
  });
  t.mock.method(console, "warn", () => {});
  t.mock.method(Date, "now", () => Date.parse(`${DAY}T12:00:00Z`));
  const oldest = groupMessage("oldest", `${DAY}T01:00:00Z`, { text: "測試資料 🌀".repeat(200) });
  const image = groupMessage("image", `${DAY}T02:00:00Z`, { type: "image" });
  const recent = Array.from({ length: 10 }, (_, i) =>
    groupMessage(`note-${i}`, `${DAY}T03:0${i}:00Z`, { text: `測試保留${i} 👩‍💻 🧑🏽‍🍳`.repeat(4) }));
  const trigger = groupMessage("trigger", `${DAY}T05:00:00Z`, { text: "工程測試 🦉" });
  const batch = [oldest, image, ...recent, trigger];
  await receive(batch, bindings, ctx);
  const full = relayPayload(fetch);
  assert.deepEqual(full.truncatedReasons, ["read_interrupted", "history_limit"]);
  const expected = {
    ...full,
    summary: "觸發前最新 10 則見 recent；較舊 1 則在 context；原因：read_interrupted、history_limit、payload_limit",
    truncatedReasons: [...full.truncatedReasons, "payload_limit"],
    contextCount: 12,
    context: full.context.slice(0, 2),
  };
  const byteLimit = Buffer.byteLength(JSON.stringify(expected));

  for (const limit of [byteLimit, byteLimit - 1]) {
    fetch.mock.resetCalls();
    await receive(batch, { ...bindings, RELAY_MAX_PAYLOAD_BYTES: String(limit) }, ctx);
    const payload = relayPayload(fetch);
    const body = relayRequest(fetch).body;
    assert.ok(Buffer.byteLength(body) <= limit);
    assert.equal(payload.truncated, true);
    assert.deepEqual(payload.truncatedReasons, expected.truncatedReasons);
    const keepImage = limit === byteLimit;
    assert.equal(payload.contextCount, keepImage ? 12 : 11);
    assert.deepEqual(payload.context.map(({ messageId }) => messageId), keepImage ? ["trigger", "image"] : ["trigger"]);
    if (keepImage) {
      assert.equal(Buffer.byteLength(body), byteLimit);
      assert.equal(typeof payload.context[1].downloadUrl, "string");
      assert.equal(payload.context[1].downloadUrl, expected.context[1].downloadUrl);
    }
    assert.deepEqual(payload.recent.map(({ text }) => text), recent.toReversed().map(({ message }) => message.text));
    assert.equal(payload.text, trigger.message.text);
    assert.equal(payload.context[0].text, trigger.message.text);
    assert.equal(payload.context[0].isTrigger, true);
  }
});


test("indexes Taipei 23:59 and 00:01 under different dates despite the same UTC day", async (t) => {
  const kv = memoryKV(t);
  const { fetch, ctx } = mockRelay(t);
  const bindings = { ...env, CHAT_HISTORY: kv };
  const yesterday = groupMessage("yesterday", "2026-11-24T15:59:00Z", { text: "測試前日" });
  const today = groupMessage("today", "2026-11-24T16:01:00Z", { text: "測試當日" });
  const trigger = groupMessage("trigger", "2026-11-24T16:02:00Z", { text: "工程測試" });
  await receive([yesterday, today], bindings, ctx);
  assert.deepEqual([...kv.values.keys()].map((key) => key.split(":")[2]), ["2026-11-24", DAY]);
  moveToLegacyHistory(kv);
  await receive([yesterday, today], bindings, ctx);
  await receive([trigger], bindings, ctx);

  const payload = relayPayload(fetch);
  assert.equal(payload.taipeiDate, DAY);
  assert.deepEqual(payload.recent.map(({ messageId }) => messageId), ["today"]);
  assert.deepEqual(payload.context.map(({ messageId }) => messageId), ["trigger"]);
  assert.equal(payload.truncated, false);
  assert.equal(Object.hasOwn(payload, "truncatedReasons"), false);
  assert.deepEqual(kv.list.mock.calls.map(({ arguments: [{ prefix }] }) => prefix.split(":")[2]), [DAY, DAY]);
});

test("merges same-batch messages from memory when KV writes fail", async (t) => {
  const kv = memoryKV(t);
  kv.put.mock.mockImplementation(async () => { throw new Error("test write failure"); });
  const warn = t.mock.method(console, "warn", () => {});
  const { fetch, ctx } = mockRelay(t);
  const note = groupMessage("note", `${DAY}T01:00:00Z`, { text: "測試同批 🪴" });
  const trigger = groupMessage("trigger", `${DAY}T02:00:00Z`, { text: "工程測試" });
  await receive([trigger, note], { ...env, CHAT_HISTORY: kv }, ctx);

  const payload = relayPayload(fetch);
  assert.equal(kv.values.size, 0);
  assert.equal(warn.mock.callCount(), 2);
  assert.deepEqual(payload.recent.map(({ text, isTrigger }) => [text, isTrigger]), [[note.message.text, false]]);
  assert.deepEqual(payload.context.map(({ text, isTrigger }) => [text, isTrigger]), [[trigger.message.text, true]]);
});

test("deduplicates both formats before applying the history limit and merges by timestamp", async (t) => {
  const kv = memoryKV(t, { pageSize: 2, eventual: true });
  const { fetch, ctx } = mockRelay(t);
  const bindings = { ...env, CHAT_HISTORY: kv, RELAY_HISTORY_LIMIT: 3 };
  const duplicate = groupMessage("duplicate", `${DAY}T03:00:00Z`, { text: "測試舊版本" });
  const legacy = groupMessage("legacy-only", `${DAY}T04:00:00Z`, { text: "測試只有舊鍵" });
  await receive([legacy, duplicate], bindings, ctx);
  moveToLegacyHistory(kv);

  const updated = { ...duplicate, message: { ...duplicate.message, text: "測試新版本" } };
  const tied = groupMessage("a-new", `${DAY}T03:00:00Z`, { text: "測試同時間" });
  const older = groupMessage("older", `${DAY}T02:00:00Z`, { text: "測試較早" });
  await receive([updated, older, tied], bindings, ctx);
  kv.publish();
  const trigger = groupMessage("trigger", `${DAY}T05:00:00Z`, { text: "工程測試" });
  await receive([trigger], bindings, ctx);

  const payload = relayPayload(fetch);
  assert.equal(payload.contextCount, 4);
  assert.equal(payload.truncated, true);
  assert.deepEqual(payload.truncatedReasons, ["history_limit"]);
  assert.deepEqual(payload.recent.map(({ messageId }) => messageId), ["legacy-only", "a-new", "duplicate"]);
  assert.deepEqual(payload.context.map(({ messageId }) => messageId), ["trigger"]);
  assert.equal(payload.recent[2].text, updated.message.text);
});

test("sorts 15-digit reverse time keys newest first across a timestamp digit boundary", async (t) => {
  const kv = memoryKV(t);
  const { ctx } = mockRelay(t);
  const timestamps = [99_999_999_999_999, 100_000_000_000_000, 99_999_999_999_998, 100_000_000_000_001];
  const messages = timestamps.map((time, i) =>
    groupMessage(`boundary-${i}`, new Date(time).toISOString(), { text: "測試進位" }));
  await receive(messages, { ...env, CHAT_HISTORY: kv }, ctx);

  const keys = [...kv.values.keys()].sort();
  assert.deepEqual(keys.map((key) => JSON.parse(kv.values.get(key)).timestampMs), [...timestamps].sort((a, b) => b - a));
  assert.deepEqual(keys.map((key) => key.split(":").slice(0, 4)), [
    ["msgr", "group-test", "5138-11-16", "899999999999998"],
    ["msgr", "group-test", "5138-11-16", "899999999999999"],
    ["msgr", "group-test", "5138-11-16", "900000000000000"],
    ["msgr", "group-test", "5138-11-16", "900000000000001"],
  ]);
});

test("isolates media failures and logs only fixed text or HTTP status codes", async (t) => {
  const warn = t.mock.method(console, "warn", () => {});
  const log = t.mock.method(console, "log", () => {});
  const error = t.mock.method(console, "error", () => {});
  const kv = memoryKV(t);
  const token = randomBytes(32).toString("hex");
  const note = groupMessage("note", `${DAY}T04:00:00Z`, { text: "機密進度 https://example.invalid/private" });
  const sensitive = [note.message.text, note.source.groupId, note.source.userId, token,
    env.LINE_CHANNEL_SECRET, env.RELAY_SIGNING_SECRET].join(" ");
  const { ctx } = mockFetch(t, async (url) => {
    if (url.endsWith("/http-error/content")) return new Response(sensitive, { status: 302 });
    if (url.endsWith("/r2-error/content")) return new Response(sensitive);
    throw new Error(sensitive);
  });
  const media = ["http-error", "fetch-error", "r2-error"].map((id) =>
    groupMessage(id, `${DAY}T05:00:00Z`, { type: "image" }));

  await receive([note, ...media], {
    ...env, CHAT_HISTORY: kv, LINE_CHANNEL_ACCESS_TOKEN: token,
    MEDIA_BUCKET: { put: async () => { throw new Error(sensitive); } },
  }, ctx);
  assert.deepEqual(savedMessages(kv).slice(1).map(({ media }) => media.status),
    ["download_failed", "download_failed", "storage_failed"]);
  assert.deepEqual(warn.mock.calls.map(({ arguments: args }) => args), [["Media storage write failed"]]);
  assert.equal(log.mock.callCount(), 0);
  assert.equal(error.mock.callCount(), 0);
});

for (const morningCount of [44, 47]) {
  test(`keeps the evening messages intact in 3 and 6 KiB prefixes with ${morningCount + 4} total messages`, async (t) => {
    const day = "2026-11-28";
    const kv = memoryKV(t);
    const bindings = {
      ...env, CHAT_HISTORY: kv, MEDIA_BUCKET: memoryR2(t),
      LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex"),
    };
    const { fetch, ctx } = mockFetch(t, async (url) => {
      if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
      if (url.startsWith(LINE_PROFILE_ROOT)) return new Response(null, { status: 404 });
      return new Response(new Uint8Array([1, 2, 3]), { headers: { "Content-Type": "image/png" } });
    });
    const morning = Array.from({ length: morningCount }, (_, i) =>
      groupMessage(`prefix-morning-${i}`, `${day}T01:${String(i).padStart(2, "0")}:00Z`,
        i < 3 ? { type: "image" } : { text: "晨間合成資料。" }));
    const image = groupMessage("prefix-image", `${day}T13:00:30Z`, { type: "image" });
    const noteA = groupMessage("prefix-note-a", `${day}T13:00:40Z`, { text: "合成晚間樣本甲 👩‍💻" });
    const noteB = groupMessage("prefix-note-b", `${day}T13:00:48Z`, { text: "合成晚間樣本乙 🧪" });
    const trigger = groupMessage("prefix-trigger", `${day}T13:02:55Z`, { text: "工程轉發合成樣本" });
    await receive([...morning, image, noteA, noteB], bindings, ctx);
    await receive([trigger], bindings, ctx);

    const body = callsTo(fetch, env.RELAY_WEBHOOK_URL)[0].arguments[1].body;
    const bytes = Buffer.from(body);
    assert.ok(bytes.length > 6 * 1024);
    for (const size of [3 * 1024, 6 * 1024]) {
      const prefix = bytes.subarray(0, size).toString("utf8");
      for (const { message } of [noteA, noteB, trigger]) {
        assert.ok(prefix.includes(JSON.stringify(message.text)));
      }
      assert.ok(prefix.includes(encodeURIComponent(`line-media/${day}/group-test/prefix-image`)));
    }

    const payload = JSON.parse(body);
    assert.ok(body.startsWith('{"summary":'));
    assert.deepEqual(Object.keys(payload), [
      "summary", "source", "text", "timestamp", "timestampMs", "messageId",
      "webhookEventId", "userId", "recent", "recentCount", "truncated",
      ...(morningCount === 47 ? ["truncatedReasons"] : []),
      "contextCount", "groupId", "taipeiDate", "contextStart", "context",
    ]);
    const evening = [noteB, noteA, image];
    const recent = [...evening, ...morning.slice(-7).reverse()];
    assert.equal(payload.recentCount, 10);
    assert.equal(payload.contextCount, morningCount + 4);
    assert.equal(payload.summary, `觸發前最新 10 則見 recent；較舊 ${morningCount - 7} 則在 context` +
      (morningCount === 47 ? "；原因：history_limit" : ""));
    assert.deepEqual(payload.recent.map(({ messageId }) => messageId), recent.map(({ message }) => message.id));
    assert.deepEqual(payload.recent.slice(0, 3).map(({ taipeiTime }) => taipeiTime),
      [`${day} 21:00:48`, `${day} 21:00:40`, `${day} 21:00:30`]);
    assert.deepEqual(payload.context.map(({ messageId }) => messageId),
      [trigger, ...morning.slice(0, -7).reverse()].map(({ message }) => message.id));
    const sentImage = payload.recent[2];
    assert.equal(sentImage.media.status, "stored");
    assert.equal(sentImage.text, null);
    assert.equal((await worker.fetch(new Request(sentImage.downloadUrl), bindings, ctx)).status, 200);

    for (const fragment of [sentImage.downloadUrl, noteA.message.text, noteB.message.text]) {
      const position = body.indexOf(fragment);
      assert.ok(position >= 0 && Buffer.byteLength(body.slice(0, position)) < 4 * 1024);
    }
    for (const size of [3 * 1024, 6 * 1024]) {
      const prefix = bytes.subarray(0, size);
      for (const item of payload.recent.slice(0, 3)) assert.ok(prefix.includes(JSON.stringify(item)));
    }
  });
}


test("uses the 24 KiB default or valid override and removes only the oldest whole messages", async (t) => {
  const kv = memoryKV(t);
  const { fetch, ctx } = mockRelay(t);
  const bindings = { ...env, CHAT_HISTORY: kv, RELAY_HISTORY_LIMIT: "250" };
  const notes = Array.from({ length: 240 }, (_, i) => ({
    ...groupMessage(`budget-${i}`, `${DAY}T01:00:00Z`, { text: `測試${i} 中文🧪`.repeat(40) }),
    timestamp: Date.parse(`${DAY}T01:00:00Z`) + i,
  }));
  const trigger = groupMessage("budget-trigger", `${DAY}T02:00:00Z`, { text: "工程合成資料 👩‍💻" });
  await receive(notes, bindings, ctx);
  assert.equal(savedMessages(kv).length, 240);

  async function checkBudget(limit, setting) {
    fetch.mock.resetCalls();
    await receive([trigger], { ...bindings, RELAY_MAX_PAYLOAD_BYTES: setting }, ctx);
    const { body } = relayRequest(fetch);
    const payload = JSON.parse(body);
    assert.ok(Buffer.byteLength(body) <= limit);
    assert.equal(payload.truncated, true);
    assert.deepEqual(payload.truncatedReasons, ["payload_limit"]);
    const [sentTrigger, ...older] = payload.context;
    const retained = [...payload.recent, ...older];
    assert.ok(older.length > 0 && retained.length < notes.length);
    assert.deepEqual(retained.map(({ messageId }) => messageId),
      notes.toReversed().slice(0, retained.length).map(({ message }) => message.id));
    assert.deepEqual(payload.recent.map(({ text, isTrigger, textTruncated }) => [text, isTrigger, textTruncated]),
      notes.slice(-10).reverse().map(({ message }) => [message.text, false, undefined]));
    assert.equal(payload.text, trigger.message.text);
    assert.equal(sentTrigger.text, trigger.message.text);
    assert.equal(sentTrigger.isTrigger, true);
    assert.equal(payload.recentCount, 10);
    assert.equal(payload.contextCount, 1 + retained.length);
    assert.equal(payload.summary, `觸發前最新 10 則見 recent；較舊 ${older.length} 則在 context；原因：payload_limit`);
    return { body, count: payload.contextCount };
  }

  const baseline = await checkBudget(24576);
  const override = await checkBudget(65536, "65536");
  assert.ok(Buffer.byteLength(override.body) > 24576 && override.count > baseline.count);
  for (const invalid of ["", "0", "-1", "2.5", "invalid", "9007199254740992", true, [1000]]) {
    assert.deepEqual(await checkBudget(24576, invalid), baseline);
  }

  const { headers, body } = relayRequest(fetch);
  const [, time, digest] = /^t=(\d+),v1=([0-9a-f]{64})$/.exec(headers["X-Relay-Signature"]);
  assert.equal(digest, await sign(env.RELAY_SIGNING_SECRET, `${time}.${body}`, "hex"));
});

test("sends the entire trigger and recent block when they exceed the preferred budget", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const warn = t.mock.method(console, "warn", () => {});
  const notes = Array.from({ length: 11 }, (_, i) =>
    groupMessage(`protected-${i}`, `${DAY}T01:${String(i).padStart(2, "0")}:00Z`, { text: "晚間合成 🧪".repeat(180) }));
  const trigger = groupMessage("protected-trigger", `${DAY}T02:00:00Z`, { text: "工程" + "觸".repeat(2100) });
  await receive([...notes, trigger], env, ctx);

  const payload = relayPayload(fetch);
  assert.ok(Buffer.byteLength(relayRequest(fetch).body) > 24576);
  assert.equal(payload.text, trigger.message.text);
  assert.deepEqual(payload.context.map(({ messageId, text, isTrigger }) => [messageId, text, isTrigger]),
    [[trigger.message.id, trigger.message.text, true]]);
  assert.deepEqual(payload.recent.map(({ text, messageId, textTruncated }) => [text, messageId, textTruncated]),
    notes.slice(1).reverse().map(({ message }) => [message.text, message.id, undefined]));
  assert.equal(payload.truncated, true);
  assert.deepEqual(payload.truncatedReasons, ["payload_limit"]);
  assert.equal(payload.contextCount, 11);
  assert.equal(payload.summary, "觸發前最新 10 則見 recent；較舊 0 則在 context；原因：payload_limit");
  assert.deepEqual(warn.mock.calls.map(({ arguments: args }) => args), [["Relay payload exceeds preferred size limit"]]);
});

test("clamps an oversized override and trims older entries before enforcing the 512 KiB limit", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const warn = t.mock.method(console, "warn", () => {});
  const notes = Array.from({ length: 11 }, (_, i) =>
    groupMessage(`hard-${i}`, `${DAY}T01:${String(i).padStart(2, "0")}:00Z`, { text: "合成資料" }));
  const trigger = groupMessage("hard-trigger", `${DAY}T02:00:00Z`, { text: "工程" });
  await receive([...notes, trigger], { ...env, RELAY_MAX_PAYLOAD_BYTES: "1" }, ctx);
  const hardLimit = 512 * 1024;
  const initialBytes = Buffer.byteLength(relayRequest(fetch).body);
  const extra = hardLimit - initialBytes;
  trigger.message.text += "x".repeat(Math.floor(extra / 2));
  if (extra % 2) {
    for (const item of [...notes, trigger]) item.source.groupId += "x";
  }

  fetch.mock.resetCalls();
  warn.mock.resetCalls();
  await receive([...notes, trigger], { ...env, RELAY_MAX_PAYLOAD_BYTES: "1048576" }, ctx);
  const payload = relayPayload(fetch);
  assert.equal(Buffer.byteLength(relayRequest(fetch).body), hardLimit);
  assert.equal(payload.contextCount, 11);
  assert.equal(payload.context.length, 1);
  assert.equal(payload.context[0].text, trigger.message.text);
  assert.deepEqual(payload.truncatedReasons, ["payload_limit"]);
  assert.equal(warn.mock.callCount(), 0);
});

test("counts Unicode code points and preserves emoji and ZWJ graphemes at both text limits", async (t) => {
  const { fetch, ctx } = mockRelay(t);
  const notes = [
    "中".repeat(200),
    "中".repeat(199) + "🧪尾",
    "中".repeat(199) + "👩‍💻尾",
    "中".repeat(199) + "e\u0301尾",
    ...Array(7).fill("近日合成資料"),
    "中".repeat(201) + "👩‍💻",
    "中".repeat(1999) + "🧪",
    "中".repeat(1999) + "👩‍💻尾",
  ].map((text, i) =>
    groupMessage(`unicode-${i}`, `${DAY}T01:${String(i).padStart(2, "0")}:00Z`, { text }));
  const trigger = groupMessage("unicode-trigger", `${DAY}T02:00:00Z`, { text: "工程" + "x".repeat(2100) });
  await receive([...notes, trigger], { ...env, RELAY_MAX_PAYLOAD_BYTES: "65536" }, ctx);

  const { recent, context, text, truncated } = relayPayload(fetch);
  assert.equal(truncated, false);
  assert.equal(text, trigger.message.text);
  assert.equal(context[0].text, trigger.message.text);
  assert.equal(Object.hasOwn(context[0], "textTruncated"), false);
  assert.deepEqual(context.slice(1).map(({ text, textTruncated }) => [text, textTruncated]), [
    ["中".repeat(199), true],
    ["中".repeat(199), true],
    ["中".repeat(199) + "🧪", true],
    ["中".repeat(200), undefined],
  ]);
  assert.deepEqual(recent.slice(0, 3).map(({ text, textTruncated }) => [text, textTruncated]), [
    ["中".repeat(1999), true],
    [notes.at(-2).message.text, undefined],
    [notes.at(-3).message.text, undefined],
  ]);
});

test("selects only messages strictly before each trigger even if later events are already stored", async (t) => {
  const kv = memoryKV(t);
  const { fetch, ctx } = mockRelay(t);
  const bindings = { ...env, CHAT_HISTORY: kv };
  const earlier = groupMessage("before", `${DAY}T01:00:00Z`, { text: "合成前一則" });
  const trigger = groupMessage("middle", `${DAY}T02:00:00Z`, { text: "工程合成觸發" });
  const tied = groupMessage("same", `${DAY}T02:00:00Z`, { text: "同時間合成資料" });
  const later = groupMessage("after", `${DAY}T03:00:00Z`, { text: "合成後一則" });
  await receive([later], bindings, ctx);
  await receive([trigger, tied, earlier], bindings, ctx);
  const { recent, context, contextCount } = relayPayload(fetch);
  assert.deepEqual(recent.map(({ messageId }) => messageId), ["before"]);
  assert.deepEqual(context.map(({ messageId }) => messageId), ["middle"]);
  assert.equal(contextCount, 2);
  assert.equal(savedMessages(kv).length, 4);
});


function assertOutboundRequests(fetch, profileUrls = []) {
  const requests = fetch.mock.calls.map(({ arguments: [url, { method }] }) => [method, url]);
  assert.deepEqual(requests.sort(),
    [["POST", env.RELAY_WEBHOOK_URL], ...profileUrls.map((url) => ["GET", url])].sort());
}

test("deduplicates recent and trigger profiles, caches only names, and calls only profile GET and relay POST", async (t) => {
  const kv = memoryKV(t);
  const bindings = { ...env, CHAT_HISTORY: kv, LINE_CHANNEL_ACCESS_TOKEN: randomBytes(32).toString("hex") };
  const groupId = "group/demo";
  const userId = "user/demo";
  const alternateId = "user-alt";
  const senderUrl = `${LINE_PROFILE_ROOT}group%2Fdemo/member/user%2Fdemo`;
  const alternateUrl = `${LINE_PROFILE_ROOT}group%2Fdemo/member/user-alt`;
  const { fetch, ctx } = mockFetch(t, async (url) => {
    if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
    const displayName = new Map([[senderUrl, "樣本甲"], [alternateUrl, "樣本乙"]]).get(url);
    return Response.json({ displayName, pictureUrl: "ignored", statusMessage: "ignored" });
  });
  const notes = Array.from({ length: 11 }, (_, i) => {
    const note = groupMessage(`profile-${i}`, `${DAY}T01:${String(i).padStart(2, "0")}:00Z`, { text: "合成資料" }, groupId);
    note.source.userId = i === 0 ? "older-author" : i === 1 ? null : i % 2 === 0 ? alternateId : userId;
    return note;
  });
  const trigger = groupMessage("named-trigger", `${DAY}T02:00:00Z`, { text: "工程合成資料" }, groupId);
  trigger.source.userId = userId;
  await receive([...notes, trigger], bindings, ctx);

  assertOutboundRequests(fetch, [senderUrl, alternateUrl]);
  for (const url of [senderUrl, alternateUrl]) {
    const { headers, redirect } = callsTo(fetch, url)[0].arguments[1];
    assert.equal(redirect, "manual");
    assert.ok(new Headers(headers).get("Authorization") === `Bearer ${bindings.LINE_CHANNEL_ACCESS_TOKEN}`);
  }
  const payload = relayPayload(fetch);
  assert.equal(payload.senderName, "樣本甲");
  assert.equal(payload.context[0].senderName, "樣本甲");
  assert.equal(Object.hasOwn(payload.context[1], "senderName"), false);
  assert.deepEqual(payload.recent.map(({ senderName }) => senderName),
    notes.slice(1).reverse().map(({ source }) =>
      ({ [userId]: "樣本甲", [alternateId]: "樣本乙" })[source.userId]));
  assert.equal(Object.hasOwn(payload.recent.at(-1), "senderName"), false);
  const profileWrites = kv.put.mock.calls.map(({ arguments: args }) => args)
    .filter(([key]) => key.startsWith("profile:"));
  assert.deepEqual(profileWrites, [
    ["profile:group_demo:user_demo", "樣本甲", { expirationTtl: 86400 }],
    ["profile:group_demo:user-alt", "樣本乙", { expirationTtl: 86400 }],
  ]);
  assert.ok(savedMessages(kv).every((record) => !Object.hasOwn(record, "senderName")));

  fetch.mock.resetCalls();
  kv.put.mock.resetCalls();
  await receive([trigger], bindings, ctx);
  assertOutboundRequests(fetch);
  assert.deepEqual(relayPayload(fetch), payload);
  assert.equal(kv.put.mock.callCount(), 1);
});

test("omits unavailable profiles after HTTP, fetch, response, or profile-cache failures", async (t) => {
  const warn = t.mock.method(console, "warn", () => {});
  const log = t.mock.method(console, "log", () => {});
  const error = t.mock.method(console, "error", () => {});
  const profileUrl = `${LINE_PROFILE_ROOT}group-test/member/user-test`;
  const sampleName = "合成樣本名";
  for (const failure of ["http", "network", "json", "name", "read", "write"]) {
    const kv = memoryKV(t);
    if (failure === "read") {
      const get = kv.get;
      kv.get = t.mock.fn(async (key, type) => {
        if (typeof key === "string") throw new Error(sampleName);
        return get(key, type);
      });
    }
    if (failure === "write") {
      const put = kv.put;
      kv.put = t.mock.fn(async (key, value, options) => {
        if (key.startsWith("profile:")) throw new Error(sampleName);
        return put(key, value, options);
      });
    }
    const { fetch, ctx } = mockFetch(t, async (url) => {
      if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
      if (failure === "http") return new Response(sampleName, { status: 403 });
      if (failure === "network") throw new Error(sampleName);
      if (failure === "json") return new Response(sampleName);
      if (failure === "name") return Response.json({ displayName: " " });
      return Response.json({ displayName: sampleName });
    });
    const note = { ...event, timestamp: event.timestamp - 1, message: { id: "profile-note", type: "text", text: "合成資料" } };
    await receive([note, event], { ...env, CHAT_HISTORY: kv, LINE_CHANNEL_ACCESS_TOKEN: "test-only" }, ctx);
    assertOutboundRequests(fetch, failure === "read" ? [] : [profileUrl]);
    const payload = relayPayload(fetch);
    for (const item of [payload, ...payload.recent, ...payload.context]) {
      assert.equal(Object.hasOwn(item, "senderName"), false, failure);
    }
    assert.ok(![...kv.values.keys()].some((key) => key.startsWith("profile:")), failure);
    fetch.mock.restore();
  }
  assert.equal(warn.mock.callCount(), 0);
  assert.equal(log.mock.callCount(), 0);
  assert.equal(error.mock.callCount(), 0);
});

test("with no profile credential there is no cache read, no LINE call, and no fallback name", async (t) => {
  const kv = memoryKV(t);
  kv.values.set("profile:group-test:user-test", "合成名稱");
  const { fetch, ctx } = mockRelay(t);
  await receive([event], { ...env, CHAT_HISTORY: kv }, ctx);

  assertOutboundRequests(fetch);
  assert.ok(kv.get.mock.calls.every(({ arguments: [key] }) => Array.isArray(key)));
  const payload = relayPayload(fetch);
  assert.equal(Object.hasOwn(payload, "senderName"), false);
  assert.equal(Object.hasOwn(payload.context[0], "senderName"), false);
});

test("runs profile lookups in parallel and forwards after 2 seconds even if fetch or KV stalls", { timeout: 2000 }, async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const kv = memoryKV(t);
  const fetchStarted = Promise.withResolvers();
  const readStarted = Promise.withResolvers();
  const quickProfileFinished = Promise.withResolvers();
  const pendingFetch = Promise.withResolvers();
  const pendingRead = Promise.withResolvers();
  const slowUrl = `${LINE_PROFILE_ROOT}group-test/member/slow-fetch`;
  const fastUrl = `${LINE_PROFILE_ROOT}group-test/member/user-test`;
  const get = kv.get;
  kv.get = t.mock.fn(async (key, type) => {
    if (key === "profile:group-test:slow-read") {
      readStarted.resolve();
      return pendingRead.promise;
    }
    return get(key, type);
  });
  const put = kv.put;
  kv.put = t.mock.fn(async (key, value, options) => {
    await put(key, value, options);
    if (key === "profile:group-test:user-test") quickProfileFinished.resolve();
  });
  const { fetch, ctx } = mockFetch(t, async (url, { signal }) => {
    if (url === env.RELAY_WEBHOOK_URL) return new Response(null, { status: 204 });
    if (url === slowUrl) {
      fetchStarted.resolve(signal);
      return pendingFetch.promise;
    }
    return Response.json({ displayName: "合成快取名" });
  });
  const warn = t.mock.method(console, "warn", () => {});
  const notes = ["slow-fetch", "slow-read"].map((userId, i) => ({
    ...event,
    source: { ...event.source, userId },
    timestamp: event.timestamp - 1 - i,
    message: { id: userId, type: "text", text: "合成資料" },
  }));
  const response = await worker.fetch(await signedPost([...notes, event]), {
    ...env, CHAT_HISTORY: kv, LINE_CHANNEL_ACCESS_TOKEN: "test-only",
  }, ctx);
  assert.equal(response.status, 200);

  const [slowSignal] = await Promise.all([fetchStarted.promise, readStarted.promise, quickProfileFinished.promise]);
  t.mock.timers.tick(1999);
  assert.equal(callsTo(fetch, env.RELAY_WEBHOOK_URL).length, 0);
  assert.equal(slowSignal.aborted, false);
  t.mock.timers.tick(1);
  await finishBackgroundWork(ctx);
  assert.equal(slowSignal.aborted, true);
  const payload = relayPayload(fetch);
  assert.equal(payload.senderName, "合成快取名");
  assert.ok(payload.recent.every((item) => !Object.hasOwn(item, "senderName")));

  pendingRead.resolve(null);
  pendingFetch.resolve(Response.json({ displayName: "合成遲到名" }));
  await new Promise(setImmediate);
  assertOutboundRequests(fetch, [slowUrl, fastUrl]);
  assert.ok(![...kv.values.keys()].some((key) => key.startsWith("profile:group-test:slow-")));
  assert.equal(warn.mock.callCount(), 0);
});
