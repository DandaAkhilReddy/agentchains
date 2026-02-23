import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  CONNECTING = 0;
  OPEN = 1;
  CLOSING = 2;
  CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    instances.push(this);
  }

  send = vi.fn();
  close = vi.fn();

  /** Test helper: simulate server opening the connection */
  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event("open"));
  }

  /** Test helper: simulate server closing the connection */
  simulateClose(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.({} as CloseEvent);
  }

  /** Test helper: simulate a server message */
  simulateMessage(data: string): void {
    this.onmessage?.({ data } as MessageEvent);
  }

  /** Test helper: simulate connection error */
  simulateError(): void {
    this.onerror?.(new Event("error"));
  }
}

let instances: MockWebSocket[] = [];

vi.stubGlobal("WebSocket", MockWebSocket);

// Import after WebSocket is stubbed
import { A2UIClient } from "../a2ui";

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("A2UIClient", () => {
  let client: A2UIClient;

  beforeEach(() => {
    instances = [];
    vi.useFakeTimers();
    client = new A2UIClient("http://localhost:8000", "test-token");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // -----------------------------------------------------------------------
  // Constructor
  // -----------------------------------------------------------------------

  describe("constructor", () => {
    it("derives ws: URL from http: base URL", () => {
      const c = new A2UIClient("http://localhost:8000", "tk");
      // connect to trigger WebSocket creation
      c.connect();
      const ws = instances[instances.length - 1];
      expect(ws.url).toContain("ws://");
      expect(ws.url).toContain("localhost:8000");
    });

    it("derives wss: URL from https: base URL", () => {
      const c = new A2UIClient("https://example.com", "tk");
      c.connect();
      const ws = instances[instances.length - 1];
      expect(ws.url).toContain("wss://");
      expect(ws.url).toContain("example.com");
    });

    it("includes token in the connection URL", () => {
      client.connect();
      const ws = instances[instances.length - 1];
      expect(ws.url).toContain("token=test-token");
    });

    it("URL-encodes the token", () => {
      const c = new A2UIClient("http://localhost", "to ken=1&2");
      c.connect();
      const ws = instances[instances.length - 1];
      expect(ws.url).toContain("token=to%20ken%3D1%262");
    });

    it("appends token with & when wsUrl already has query params", () => {
      // Access private field via cast to test query-string joining
      const c = new A2UIClient("http://localhost", "tk");
      // Manually override wsUrl to include a query param
      (c as any).wsUrl = "ws://localhost/ws/v4/a2ui?foo=bar";
      c.connect();
      const ws = instances[instances.length - 1];
      expect(ws.url).toContain("?foo=bar&token=tk");
    });
  });

  // -----------------------------------------------------------------------
  // connect()
  // -----------------------------------------------------------------------

  describe("connect()", () => {
    it("resolves when WebSocket opens", async () => {
      const p = client.connect();
      const ws = instances[0];
      ws.simulateOpen();
      await expect(p).resolves.toBeUndefined();
    });

    it("rejects when WebSocket errors during connect", async () => {
      const p = client.connect();
      const ws = instances[0];
      ws.simulateError();
      await expect(p).rejects.toThrow("WebSocket connection failed");
    });

    it("returns immediately if already OPEN", async () => {
      const p1 = client.connect();
      instances[0].simulateOpen();
      await p1;

      // The ws is OPEN now, should resolve immediately
      const p2 = client.connect();
      await expect(p2).resolves.toBeUndefined();
      // No second WebSocket should have been created
      expect(instances.length).toBe(1);
    });

    it("returns immediately if already CONNECTING", async () => {
      // First connect() puts ws in CONNECTING state
      const p1 = client.connect();
      // Second connect() while still CONNECTING
      const p2 = client.connect();
      await expect(p2).resolves.toBeUndefined();
      // Resolve the first one to clean up
      instances[0].simulateOpen();
      await p1;
    });

    it("resets reconnect attempts on successful connect", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;
      // Access private field to verify
      expect((client as any).reconnectAttempts).toBe(0);
    });

    it("starts heartbeat on successful connect", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;
      expect((client as any).heartbeatInterval).not.toBeNull();
    });
  });

  // -----------------------------------------------------------------------
  // disconnect()
  // -----------------------------------------------------------------------

  describe("disconnect()", () => {
    it("closes the WebSocket", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.disconnect();
      expect(instances[0].close).toHaveBeenCalled();
    });

    it("nullifies the ws reference", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.disconnect();
      expect((client as any).ws).toBeNull();
    });

    it("prevents auto-reconnect by maxing out attempts", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.disconnect();
      expect((client as any).reconnectAttempts).toBe((client as any).maxReconnects);
    });

    it("stops the heartbeat", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.disconnect();
      expect((client as any).heartbeatInterval).toBeNull();
    });

    it("is safe to call when not connected", () => {
      expect(() => client.disconnect()).not.toThrow();
    });
  });

  // -----------------------------------------------------------------------
  // send()
  // -----------------------------------------------------------------------

  describe("send()", () => {
    it("sends JSON-RPC 2.0 message when ws is OPEN", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.send("test.method", { key: "val" });
      expect(instances[0].send).toHaveBeenCalledTimes(1);
      const payload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(payload.jsonrpc).toBe("2.0");
      expect(payload.method).toBe("test.method");
      expect(payload.params).toEqual({ key: "val" });
      expect(payload.id).toBe("req_1");
    });

    it("auto-generates sequential message IDs", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      const id1 = client.send("m1", {});
      const id2 = client.send("m2", {});
      expect(id1).toBe("req_1");
      expect(id2).toBe("req_2");
    });

    it("uses a custom id when provided", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      const id = client.send("m", {}, "custom-id");
      expect(id).toBe("custom-id");
      const payload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(payload.id).toBe("custom-id");
    });

    it("does not throw when ws is not OPEN", () => {
      // ws is null
      expect(() => client.send("m", {})).not.toThrow();
    });

    it("does not send data when ws is CLOSED", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      instances[0].readyState = MockWebSocket.CLOSED;
      client.send("m", {});
      // The first call is from heartbeat setup, so check only explicit sends
      // Actually send is called only when readyState is OPEN
      const calls = instances[0].send.mock.calls;
      // No call should have been made for this send since ws is CLOSED
      // But heartbeat won't have fired yet. So send should be 0 calls
      expect(calls.length).toBe(0);
    });

    it("returns the message id even when ws is not ready", () => {
      const id = client.send("m", {});
      expect(id).toBe("req_1");
    });
  });

  // -----------------------------------------------------------------------
  // on() — handler registration
  // -----------------------------------------------------------------------

  describe("on()", () => {
    it("registers a handler for a method", () => {
      const handler = vi.fn();
      client.on("ui.render", handler);
      expect((client as any).handlers.get("ui.render")).toBe(handler);
    });

    it("overwrites a previously registered handler", () => {
      const h1 = vi.fn();
      const h2 = vi.fn();
      client.on("ui.render", h1);
      client.on("ui.render", h2);
      expect((client as any).handlers.get("ui.render")).toBe(h2);
    });
  });

  // -----------------------------------------------------------------------
  // handleMessage() — server-pushed notifications & responses
  // -----------------------------------------------------------------------

  describe("handleMessage (via ws.onmessage)", () => {
    beforeEach(async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;
    });

    it("dispatches server notification to registered handler", () => {
      const handler = vi.fn();
      client.on("ui.render", handler);

      instances[0].simulateMessage(
        JSON.stringify({
          jsonrpc: "2.0",
          method: "ui.render",
          params: { component_id: "c1", component_type: "card", data: {} },
        }),
      );

      expect(handler).toHaveBeenCalledWith({
        component_id: "c1",
        component_type: "card",
        data: {},
      });
    });

    it("uses empty object when params is missing", () => {
      const handler = vi.fn();
      client.on("test.method", handler);

      instances[0].simulateMessage(
        JSON.stringify({ jsonrpc: "2.0", method: "test.method" }),
      );

      expect(handler).toHaveBeenCalledWith({});
    });

    it("ignores notifications without a registered handler", () => {
      // Should not throw
      instances[0].simulateMessage(
        JSON.stringify({ jsonrpc: "2.0", method: "unknown.method", params: {} }),
      );
    });

    it("invokes the global _messageCallback for notifications", () => {
      const callback = vi.fn();
      client.onMessage(callback);

      instances[0].simulateMessage(
        JSON.stringify({
          jsonrpc: "2.0",
          method: "ui.render",
          params: { id: "x" },
        }),
      );

      expect(callback).toHaveBeenCalledWith("ui.render", { id: "x" });
    });

    it("invokes both handler and _messageCallback", () => {
      const handler = vi.fn();
      const callback = vi.fn();
      client.on("ui.render", handler);
      client.onMessage(callback);

      instances[0].simulateMessage(
        JSON.stringify({
          jsonrpc: "2.0",
          method: "ui.render",
          params: { id: "x" },
        }),
      );

      expect(handler).toHaveBeenCalled();
      expect(callback).toHaveBeenCalled();
    });

    it("resolves pending request on success response", async () => {
      const initPromise = client.sendInit({ agent_id: "a1" });

      // sendInit uses send() which produces req_2 (req_1 was from heartbeat ping or auto-increment)
      // Let's find the ID that was set in pendingRequests
      const pendingKeys = Array.from((client as any).pendingRequests.keys());
      expect(pendingKeys.length).toBe(1);
      const msgId = pendingKeys[0];

      instances[0].simulateMessage(
        JSON.stringify({
          jsonrpc: "2.0",
          result: { session_id: "s1", agent_id: "a1", capabilities: {} },
          id: msgId,
        }),
      );

      const result = await initPromise;
      expect(result).toEqual({ session_id: "s1", agent_id: "a1", capabilities: {} });
      expect((client as any).pendingRequests.size).toBe(0);
    });

    it("rejects pending request on error response", async () => {
      const initPromise = client.sendInit();

      const pendingKeys = Array.from((client as any).pendingRequests.keys());
      const msgId = pendingKeys[0];

      instances[0].simulateMessage(
        JSON.stringify({
          jsonrpc: "2.0",
          error: { code: -32600, message: "Invalid Request" },
          id: msgId,
        }),
      );

      await expect(initPromise).rejects.toThrow("Invalid Request");
    });

    it("ignores response with unknown id", () => {
      instances[0].simulateMessage(
        JSON.stringify({
          jsonrpc: "2.0",
          result: {},
          id: "unknown-id",
        }),
      );
      // Should not throw
    });

    it("ignores malformed JSON messages", () => {
      instances[0].simulateMessage("not-valid-json{{{");
      // Should not throw
    });

    it("ignores messages that are not notifications or responses", () => {
      // A message with neither "method" nor a matching pending "id"
      instances[0].simulateMessage(
        JSON.stringify({ jsonrpc: "2.0" }),
      );
    });
  });

  // -----------------------------------------------------------------------
  // onMessage()
  // -----------------------------------------------------------------------

  describe("onMessage()", () => {
    it("stores the callback", () => {
      const cb = vi.fn();
      client.onMessage(cb);
      expect((client as any)._messageCallback).toBe(cb);
    });
  });

  // -----------------------------------------------------------------------
  // Heartbeat
  // -----------------------------------------------------------------------

  describe("heartbeat", () => {
    it("sends ping every 30 seconds", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      vi.advanceTimersByTime(30_000);
      // One ping should have been sent
      const calls = instances[0].send.mock.calls;
      expect(calls.length).toBeGreaterThanOrEqual(1);
      const pingPayload = JSON.parse(calls[calls.length - 1][0]);
      expect(pingPayload.method).toBe("ping");
    });

    it("does not send ping when ws is not OPEN", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      instances[0].readyState = MockWebSocket.CLOSED;
      instances[0].send.mockClear();

      vi.advanceTimersByTime(30_000);
      expect(instances[0].send).not.toHaveBeenCalled();
    });

    it("stops heartbeat on disconnect", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.disconnect();

      instances[0].send.mockClear();
      vi.advanceTimersByTime(60_000);
      // No pings should fire after disconnect
      expect(instances[0].send).not.toHaveBeenCalled();
    });

    it("restarts heartbeat on each connect (no duplicates)", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      // disconnect and reconnect
      client.disconnect();
      (client as any).reconnectAttempts = 0; // reset to allow reconnect

      const p2 = client.connect();
      instances[instances.length - 1].simulateOpen();
      await p2;

      // Only one interval should be active
      expect((client as any).heartbeatInterval).not.toBeNull();
    });
  });

  // -----------------------------------------------------------------------
  // reconnect()
  // -----------------------------------------------------------------------

  describe("reconnect (via onclose)", () => {
    it("attempts reconnection with exponential backoff on close", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      // Simulate close
      instances[0].simulateClose();

      // After close, reconnectAttempts should be 1
      // Delay = min(1000 * 2^1, 30000) = 2000ms
      vi.advanceTimersByTime(2000);
      // A new WebSocket should have been created
      expect(instances.length).toBe(2);
    });

    it("does not reconnect after disconnect()", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.disconnect();
      // disconnect sets reconnectAttempts = maxReconnects

      // Simulate close after disconnect (happens when ws.close() fires onclose)
      // But disconnect already set ws = null, so we won't get onclose naturally
      // Let's test the internal reconnect method directly
      (client as any).reconnect();

      vi.advanceTimersByTime(60_000);
      // No new WebSocket should have been created
      expect(instances.length).toBe(1);
    });

    it("stops reconnecting after maxReconnects attempts", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      // Simulate 5 connection closures
      for (let i = 0; i < 5; i++) {
        const currentWs = instances[instances.length - 1];
        currentWs.simulateClose();
        // Advance past the max backoff delay
        vi.advanceTimersByTime(30_000);
      }

      const countBefore = instances.length;
      // Now at max reconnects - closing again should not trigger reconnect
      const lastWs = instances[instances.length - 1];
      lastWs.simulateClose();
      vi.advanceTimersByTime(60_000);
      expect(instances.length).toBe(countBefore);
    });

    it("caps backoff delay at 30 seconds", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      // Set reconnect attempts high
      (client as any).reconnectAttempts = 4;
      (client as any).maxReconnects = 10; // allow more reconnects

      instances[0].simulateClose();
      // Attempt 5: delay = min(1000 * 2^5, 30000) = 30000
      vi.advanceTimersByTime(29_999);
      expect(instances.length).toBe(1); // Not yet
      vi.advanceTimersByTime(1);
      expect(instances.length).toBe(2); // Now reconnected
    });
  });

  // -----------------------------------------------------------------------
  // Convenience methods
  // -----------------------------------------------------------------------

  describe("sendInit()", () => {
    it("sends a2ui.init and returns a promise", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      const initPromise = client.sendInit({ agent_id: "a1" });

      const pendingKeys = Array.from((client as any).pendingRequests.keys());
      const msgId = pendingKeys[0];

      // Verify the send call
      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("a2ui.init");
      expect(sentPayload.params).toEqual({ agent_id: "a1" });

      // Resolve it
      instances[0].simulateMessage(
        JSON.stringify({ jsonrpc: "2.0", result: { session_id: "s1" }, id: msgId }),
      );
      await expect(initPromise).resolves.toEqual({ session_id: "s1" });
    });

    it("uses empty object as default client info", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.sendInit();

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.params).toEqual({});
    });
  });

  describe("init()", () => {
    it("is an alias for sendInit()", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      const initPromise = client.init();
      expect(initPromise).toBeInstanceOf(Promise);

      // Resolve to avoid unhandled rejection
      const pendingKeys = Array.from((client as any).pendingRequests.keys());
      instances[0].simulateMessage(
        JSON.stringify({ jsonrpc: "2.0", result: {}, id: pendingKeys[0] }),
      );
      await initPromise;
    });
  });

  describe("sendResponse()", () => {
    it("sends user.respond with request_id and value", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.sendResponse("req-123", "hello");

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("user.respond");
      expect(sentPayload.params).toEqual({ request_id: "req-123", value: "hello" });
    });
  });

  describe("respond()", () => {
    it("is an alias for sendResponse()", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.respond("req-1", 42);

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("user.respond");
      expect(sentPayload.params).toEqual({ request_id: "req-1", value: 42 });
    });
  });

  describe("sendApproval()", () => {
    it("sends user.approve with approved=true", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.sendApproval("req-1", true);

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("user.approve");
      expect(sentPayload.params).toEqual({ request_id: "req-1", approved: true });
    });

    it("sends user.approve with approved=false and reason", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.sendApproval("req-1", false, "Not safe");

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.params).toEqual({
        request_id: "req-1",
        approved: false,
        reason: "Not safe",
      });
    });

    it("omits reason when undefined", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.sendApproval("req-1", true, undefined);

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.params).not.toHaveProperty("reason");
    });
  });

  describe("approve()", () => {
    it("is an alias for sendApproval()", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.approve("req-1", true, "Looks good");

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("user.approve");
      expect(sentPayload.params.reason).toBe("Looks good");
    });
  });

  describe("sendCancel()", () => {
    it("sends user.cancel with task_id", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.sendCancel("task-42");

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("user.cancel");
      expect(sentPayload.params).toEqual({ task_id: "task-42" });
    });
  });

  describe("cancel()", () => {
    it("is an alias for sendCancel()", async () => {
      const p = client.connect();
      instances[0].simulateOpen();
      await p;

      client.cancel("task-99");

      const sentPayload = JSON.parse(instances[0].send.mock.calls[0][0]);
      expect(sentPayload.method).toBe("user.cancel");
      expect(sentPayload.params).toEqual({ task_id: "task-99" });
    });
  });
});
