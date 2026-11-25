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
  const delivery = new Promise((resolve) => { completeDelivery = resolve; });
  const { fetch, ctx } = mockRelay(t, () => delivery);
  const rawBody = `{\r\n  "events": [ ${JSON.stringify(event)} ]\r\n}\n`;

  try {
    const response = await worker.fetch(post(rawBody, await lineSignature(rawBody)), env, ctx);
    assert.equal(response.status, 200);
    assert.equal(ctx.waitUntil.mock.callCount(), 1);
    assert.equal(fetch.mock.callCount(), 1);

    const [url, request] = fetch.mock.calls[0].arguments;
    assert.equal(url, env.RELAY_WEBHOOK_URL);
    assert.equal(request.method, "POST");
    assert.equal(request.redirect, "manual");
    const headers = new Headers(request.headers);
    assert.equal(headers.get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(request.body), {
      source: "line",
      groupId: event.source.groupId,
      userId: event.source.userId,
      text: event.message.text,
      timestamp: "2026-01-02T03:04:05.678Z",
      timestampMs: event.timestamp,
      messageId: event.message.id,
      webhookEventId: event.webhookEventId,
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
  const response = await worker.fetch(post(`${body}\n`, await lineSignature(body)), env, ctx);
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
  const response = await worker.fetch(post(JSON.stringify({ events: [event] })), env, ctx);
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
  const response = await worker.fetch(new Request("https://worker.example.invalid/"), env, ctx);
  assert.equal(response.status, 405);
  assert.equal(response.headers.get("Allow"), "POST");
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
