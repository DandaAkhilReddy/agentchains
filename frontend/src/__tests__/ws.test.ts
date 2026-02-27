import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── MockWebSocket ─────────────────────────────────────────────────────────────
//
// We define this at module scope so TypeScript can reference it as a type.
// The actual global that ws.ts sees is replaced per-test in beforeEach so
// each test gets its own socket-capture array.

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  readyState = MockWebSocket.CONNECTING;
  url: string;
  onmessage: ((evt: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onopen: (() => void) | null = null;
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
  });

  constructor(url: string) {
    this.url = url;
  }
}

// Stub globals at module-parse time so they exist for the initial import.
vi.stubGlobal("WebSocket", MockWebSocket);
vi.stubGlobal("fetch", vi.fn());

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Flushes the microtask queue (Promise chains) completely.
 * One await per .then() / async hop in resolveSocketUrl.
 */
async function flushMicrotasks(depth = 10): Promise<void> {
  for (let i = 0; i < depth; i++) {
    await Promise.resolve();
  }
}

/**
 * Returns a fresh MarketplaceFeed instance.
 * We do NOT use resetModules here because that wipes out the stubGlobal
 * WebSocket reference and causes the new module to see an undefined WebSocket
 * at import time.  Instead we instantiate a new class directly by grabbing
 * the unexported class via a helper in the singleton module — but since the
 * class is not exported we instead reset the singleton's internal state by
 * disconnecting it and returning a new instance from a helper factory.
 *
 * The simplest approach: import the module once per suite and use a
 * per-test teardown to reset state via public API (setToken(null),
 * disconnect).  For tests that need a truly clean instance we create
 * our own feed instance by importing the class — but it isn't exported.
 *
 * Pragmatic solution: re-import via resetModules but also re-stub globals
 * immediately after so the new module sees the right constructors.
 */
async function freshFeed(createdSockets: MockWebSocket[]) {
  vi.resetModules();

  // After resetModules the new ws.ts module will capture whatever `WebSocket`
  // is on the global at the time of its first import.  Re-stub right before
  // importing so the module closure captures this specific spy class.
  const TrackingWS = class extends MockWebSocket {
    constructor(url: string) {
      super(url);
      createdSockets.push(this);
    }
  };
  // Copy static constants that ws.ts reads via WebSocket.OPEN / CONNECTING.
  (TrackingWS as typeof MockWebSocket).OPEN = MockWebSocket.OPEN;
  (TrackingWS as typeof MockWebSocket).CONNECTING = MockWebSocket.CONNECTING;
  vi.stubGlobal("WebSocket", TrackingWS);

  const mod = await import("../lib/ws");
  return mod.feed;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("MarketplaceFeed — ws.ts", () => {
  let createdSockets: MockWebSocket[];

  beforeEach(() => {
    createdSockets = [];
    vi.mocked(fetch).mockReset();

    // Ensure window.location looks like http so tests are predictable.
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        protocol: "http:",
        host: "localhost:5173",
      },
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  // ── 1. No token → /ws/feed ──────────────────────────────────────────────────
  it("connect without token creates ws to /ws/feed", async () => {
    const f = await freshFeed(createdSockets);
    f.connect();

    expect(createdSockets).toHaveLength(1);
    expect(createdSockets[0].url).toBe("ws://localhost:5173/ws/feed");
  });

  // ── 2. Token present + successful stream-token fetch ────────────────────────
  it("connect with token fetches stream-token and uses it", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ stream_token: "tok123" }),
    } as Response);

    const f = await freshFeed(createdSockets);
    f.setToken("my-jwt");
    f.connect();

    // resolveSocketUrl: fetch() → response.json() → .then(url) → new WebSocket
    // Each hop is an async microtask turn.  Flush generously.
    await flushMicrotasks(20);

    expect(fetch).toHaveBeenCalledWith(
      "/api/v2/events/stream-token",
      expect.objectContaining({
        headers: { Authorization: "Bearer my-jwt" },
      }),
    );
    expect(createdSockets).toHaveLength(1);
    expect(createdSockets[0].url).toBe(
      "ws://localhost:5173/ws/v2/events?token=tok123",
    );
  });

  // ── 3. Fetch throws → fallback to legacy /ws/feed?token= ─────────────────
  it("connect falls back to legacy path when stream-token fetch fails", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("network down"));

    const f = await freshFeed(createdSockets);
    f.setToken("jwt-abc");
    f.connect();

    await flushMicrotasks(20);

    expect(createdSockets).toHaveLength(1);
    expect(createdSockets[0].url).toBe(
      "ws://localhost:5173/ws/feed?token=jwt-abc",
    );
  });

  // ── 4. Response.ok but no stream_token field → fallback ──────────────────
  it("connect falls back when response has no stream_token", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ other_field: "value" }),
    } as Response);

    const f = await freshFeed(createdSockets);
    f.setToken("jwt-xyz");
    f.connect();

    await flushMicrotasks(20);

    expect(createdSockets).toHaveLength(1);
    expect(createdSockets[0].url).toBe(
      "ws://localhost:5173/ws/feed?token=jwt-xyz",
    );
  });

  // ── 5. Response has ws_url → use it instead of default ───────────────────
  it("connect uses ws_url from response when provided", async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        stream_token: "tok456",
        ws_url: "/ws/custom",
      }),
    } as Response);

    const f = await freshFeed(createdSockets);
    f.setToken("jwt-q");
    f.connect();

    await flushMicrotasks(20);

    expect(createdSockets).toHaveLength(1);
    expect(createdSockets[0].url).toBe(
      "ws://localhost:5173/ws/custom?token=tok456",
    );
  });

  // ── 6. Skip when already OPEN ────────────────────────────────────────────
  it("connect skips if already OPEN", async () => {
    const f = await freshFeed(createdSockets);
    f.connect(); // creates first socket (readyState = CONNECTING = 0)

    // Manually set the created socket to OPEN.
    createdSockets[0].readyState = MockWebSocket.OPEN;

    f.connect(); // should not create another socket

    expect(createdSockets).toHaveLength(1);
  });

  // ── 7. Skip when already CONNECTING ─────────────────────────────────────
  it("connect skips if already CONNECTING", async () => {
    const f = await freshFeed(createdSockets);
    f.connect(); // creates socket with readyState = 0 (CONNECTING)

    // readyState is still CONNECTING, so calling connect again skips.
    f.connect();

    expect(createdSockets).toHaveLength(1);
  });

  // ── 8. subscribe + unsubscribe ───────────────────────────────────────────
  it("subscribe adds listener and returns unsubscribe", async () => {
    const f = await freshFeed(createdSockets);
    const cb = vi.fn();

    const unsub = f.subscribe(cb);
    f.connect();

    const ws = createdSockets[0];
    ws.onmessage?.({ data: JSON.stringify({ type: "ping", timestamp: "t", data: {} }) });

    expect(cb).toHaveBeenCalledTimes(1);

    unsub();
    ws.onmessage?.({ data: JSON.stringify({ type: "ping", timestamp: "t", data: {} }) });

    // Still 1 — listener was removed.
    expect(cb).toHaveBeenCalledTimes(1);
  });

  // ── 9. onmessage parses JSON and notifies all listeners ──────────────────
  it("onmessage parses JSON and notifies listeners", async () => {
    const f = await freshFeed(createdSockets);
    const cb1 = vi.fn();
    const cb2 = vi.fn();

    f.subscribe(cb1);
    f.subscribe(cb2);
    f.connect();

    const payload = { type: "listing_created", timestamp: "2024-01-01", data: {} };
    createdSockets[0].onmessage?.({ data: JSON.stringify(payload) });

    expect(cb1).toHaveBeenCalledWith(payload);
    expect(cb2).toHaveBeenCalledWith(payload);
  });

  // ── 10. onmessage ignores malformed JSON ────────────────────────────────
  it("onmessage ignores malformed JSON", async () => {
    const f = await freshFeed(createdSockets);
    const cb = vi.fn();
    f.subscribe(cb);
    f.connect();

    // Should not throw.
    expect(() =>
      createdSockets[0].onmessage?.({ data: "not-json{{{{" }),
    ).not.toThrow();

    expect(cb).not.toHaveBeenCalled();
  });

  // ── 11. onclose triggers reconnect with exponential backoff ─────────────
  //
  // The key insight: when onclose fires, connect() is called again.
  // connect() guards against reconnecting when this.ws.readyState is
  // OPEN or CONNECTING.  We must set the closed socket's readyState to
  // CLOSED (3) before triggering onclose so the guard doesn't short-circuit.
  it("onclose triggers reconnect with exponential backoff", async () => {
    vi.useFakeTimers();

    const f = await freshFeed(createdSockets);
    f.connect();

    const ws1 = createdSockets[0];

    // Mark socket as closed before triggering onclose handler.
    ws1.readyState = MockWebSocket.CLOSED;
    ws1.onclose?.();
    expect(createdSockets).toHaveLength(1); // timer hasn't fired yet

    vi.advanceTimersByTime(1000);
    expect(createdSockets).toHaveLength(2); // reconnected

    // Second close — backoff doubles to 2 000 ms.
    createdSockets[1].readyState = MockWebSocket.CLOSED;
    createdSockets[1].onclose?.();
    vi.advanceTimersByTime(1999);
    expect(createdSockets).toHaveLength(2); // not yet

    vi.advanceTimersByTime(1);
    expect(createdSockets).toHaveLength(3); // fired at 2 000 ms
  });

  // ── 12. onopen resets reconnect delay ───────────────────────────────────
  it("onopen resets reconnect delay", async () => {
    vi.useFakeTimers();

    const f = await freshFeed(createdSockets);
    f.connect();

    // First close — delay bumps from 1 000 → 2 000.
    createdSockets[0].readyState = MockWebSocket.CLOSED;
    createdSockets[0].onclose?.();
    vi.advanceTimersByTime(1000); // fires at 1 000 ms → socket[1] created

    // Second close — delay bumps from 2 000 → 4 000.
    createdSockets[1].readyState = MockWebSocket.CLOSED;
    createdSockets[1].onclose?.();
    vi.advanceTimersByTime(2000); // fires at 2 000 ms → socket[2] created

    // onopen on socket[2] resets the delay back to 1 000 ms.
    createdSockets[2].onopen?.();

    createdSockets[2].readyState = MockWebSocket.CLOSED;
    createdSockets[2].onclose?.();

    vi.advanceTimersByTime(999);
    expect(createdSockets).toHaveLength(3); // not yet

    vi.advanceTimersByTime(1);
    expect(createdSockets).toHaveLength(4); // fired at 1 000 ms (reset worked)
  });

  // ── 13. disconnect closes ws and clears timer ────────────────────────────
  it("disconnect closes ws and clears timer", async () => {
    vi.useFakeTimers();

    const f = await freshFeed(createdSockets);
    f.connect();

    const ws = createdSockets[0];

    // Schedule a reconnect.
    ws.readyState = MockWebSocket.CLOSED;
    ws.onclose?.();

    // Disconnect before the timer fires.
    f.disconnect();
    expect(ws.close).toHaveBeenCalled();

    // Advance past reconnect window — no new socket should be created.
    vi.advanceTimersByTime(5000);
    expect(createdSockets).toHaveLength(1);
  });

  // ── 14. wss: protocol for https pages ────────────────────────────────────
  it("uses wss: protocol for https pages", async () => {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { protocol: "https:", host: "example.com" },
    });

    const f = await freshFeed(createdSockets);
    f.connect();

    expect(createdSockets[0].url).toBe("wss://example.com/ws/feed");
  });
});
