import { Buffer } from "node:buffer";
import { createHmac, timingSafeEqual } from "node:crypto";

const MAX_BODY_BYTES = 1024 * 1024;
const LINE_SIGNATURE_LENGTH = 44;
const decoder = new TextDecoder("utf-8", { fatal: true });

async function readBody(body) {
  if (!body) return Buffer.alloc(0);

  const reader = body.getReader();
  const chunks = [];
  let size = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return Buffer.concat(chunks, size);

      size += value.byteLength;
      if (size > MAX_BODY_BYTES) {
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

function isEngineeringMessage(event) {
  return event?.type === "message" &&
    event.source?.type === "group" &&
    event.message?.type === "text" &&
    typeof event.message.text === "string" &&
    event.message.text.includes("工程");
}

async function forwardEvent(event, env) {
  try {
    const body = JSON.stringify({
      source: "line",
      groupId: event.source.groupId,
      userId: event.source.userId ?? null,
      text: event.message.text,
      timestamp: new Date(event.timestamp).toISOString(),
      timestampMs: event.timestamp,
      messageId: event.message.id,
      webhookEventId: event.webhookEventId,
    });
    const t = Math.floor(Date.now() / 1000);
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

async function relayEvents(rawBody, env) {
  let payload;
  try {
    payload = JSON.parse(decoder.decode(rawBody));
  } catch {
    return;
  }

  if (!Array.isArray(payload?.events)) return;

  const events = payload.events.filter(isEngineeringMessage);
  if (events.length === 0) return;
  if (!env.RELAY_SIGNING_SECRET || !env.RELAY_WEBHOOK_URL) {
    console.warn("Relay configuration incomplete");
    return;
  }

  await Promise.all(events.map((event) => forwardEvent(event, env)));
}

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response(null, { status: 405, headers: { Allow: "POST" } });
    }

    let rawBody;
    try {
      rawBody = await readBody(request.body);
    } catch {
      return new Response(null, { status: 400 });
    }
    if (rawBody === null) return new Response(null, { status: 413 });

    if (!hasValidLineSignature(request.headers.get("X-Line-Signature"), rawBody, env.LINE_CHANNEL_SECRET)) {
      return new Response(null, { status: 401 });
    }

    ctx.waitUntil(Promise.resolve().then(() => relayEvents(rawBody, env)));
    return new Response(null, { status: 200 });
  },
};
