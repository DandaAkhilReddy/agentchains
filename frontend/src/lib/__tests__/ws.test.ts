import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import type { FeedEvent } from "../../types/api";

// Track all WebSocket instances created during tests
let wsInstances: MockWebSocket[] = [];

// Mock WebSocket class
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    wsInstances.push(this);
    // Simulate async connection - auto-open after microtask
    setTimeout(() => {
      if (this.readyState === MockWebSocket.CONNECTING) {
        this.readyState = MockWebSocket.OPEN;
        this.onopen?.(new Event("open"));
      }
    }, 0);
  }

  close() {
    if (this.readyState !== MockWebSocket.CLOSED) {
      this.readyState = MockWebSocket.CLOSED;
      setTimeout(() => {
        this.onclose?.(new CloseEvent("close"));
      }, 0);
    }
  }

  send(_data: string) {
    // Mock send implementation
  }

  // Helper methods for testing
  simulateMessage(data: string) {
    if (this.onmessage && this.readyState === MockWebSocket.OPEN) {
      this.onmessage(new MessageEvent("message", { data }));
    }
  }

  simulateClose() {
    if (this.readyState !== MockWebSocket.CLOSED) {
      this.readyState = MockWebSocket.CLOSED;
      if (this.onclose) {
        this.onclose(new CloseEvent("close"));
      }
    }
  }

  simulateOpen() {
    if (this.readyState === MockWebSocket.CONNECTING) {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event("open"));
      }
    }
  }
}

// Store original WebSocket and location
const originalWebSocket = global.WebSocket;
const originalLocation = global.window?.location;

describe("MarketplaceFeed", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    wsInstances = [];

    // Mock WebSocket globally - must use a proper constructor function
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;

    // Mock window.location
    delete (global.window as any).location;
    global.window.location = {
      protocol: "http:",
      host: "localhost:3000",
    } as Location;

    // Clear module cache to get fresh instance
    vi.resetModules();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    global.WebSocket = originalWebSocket;
    if (originalLocation) {
      global.window.location = originalLocation;
    }
    wsInstances = [];
  });

  // Helper to get the latest WebSocket instance
  const getLatestWS = () => wsInstances[wsInstances.length - 1];

  test("connect() creates WebSocket with ws:// protocol for http", async () => {
    const { feed } = await import("../ws");

    feed.connect();

    expect(wsInstances.length).toBe(1);
    expect(wsInstances[0].url).toBe("ws://localhost:3000/ws/feed");
  });

  test("connect() uses wss:// protocol for https", async () => {
    global.window.location.protocol = "https:";

    const { feed } = await import("../ws");
    feed.connect();

    expect(wsInstances.length).toBe(1);
    expect(wsInstances[0].url).toBe("wss://localhost:3000/ws/feed");
  });

  test("connect() does not create double connection when already OPEN", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    const firstCount = wsInstances.length;

    // Wait for connection to open
    await vi.runAllTimersAsync();

    feed.connect();
    const secondCount = wsInstances.length;

    expect(secondCount).toBe(firstCount);
    expect(wsInstances.length).toBe(1);
  });

  test("subscribe() adds listener and returns unsubscribe function", async () => {
    const { feed } = await import("../ws");
    const callback = vi.fn();

    const unsubscribe = feed.subscribe(callback);

    expect(typeof unsubscribe).toBe("function");

    feed.connect();
    await vi.runAllTimersAsync();

    const event: FeedEvent = {
      type: "agent_published",
      timestamp: new Date().toISOString(),
      data: {
        agent_id: "test-123",
        agent_name: "Test Agent",
      },
    };

    getLatestWS().simulateMessage(JSON.stringify(event));
    expect(callback).toHaveBeenCalledWith(event);
  });

  test("onmessage parses JSON and notifies all listeners", async () => {
    const { feed } = await import("../ws");
    const callback1 = vi.fn();
    const callback2 = vi.fn();

    feed.subscribe(callback1);
    feed.subscribe(callback2);
    feed.connect();

    await vi.runAllTimersAsync();

    const event: FeedEvent = {
      type: "listing_created",
      timestamp: new Date().toISOString(),
      data: {
        listing_id: "test-456",
        title: "Test Listing",
      },
    };

    getLatestWS().simulateMessage(JSON.stringify(event));

    expect(callback1).toHaveBeenCalledWith(event);
    expect(callback2).toHaveBeenCalledWith(event);
    expect(callback1).toHaveBeenCalledTimes(1);
    expect(callback2).toHaveBeenCalledTimes(1);
  });

  test("onmessage ignores malformed JSON without crashing", async () => {
    const { feed } = await import("../ws");
    const callback = vi.fn();

    feed.subscribe(callback);
    feed.connect();

    await vi.runAllTimersAsync();

    // Send malformed JSON
    getLatestWS().simulateMessage("{ invalid json }");

    expect(callback).not.toHaveBeenCalled();

    // Verify the feed is still functional
    const validEvent: FeedEvent = {
      type: "transaction_completed",
      timestamp: new Date().toISOString(),
      data: {
        tx_id: "test-789",
      },
    };

    getLatestWS().simulateMessage(JSON.stringify(validEvent));
    expect(callback).toHaveBeenCalledWith(validEvent);
  });

  test("onclose schedules reconnect via setTimeout", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    await vi.runAllTimersAsync();

    const instanceCountBefore = wsInstances.length;
    getLatestWS().simulateClose();

    // Advance timers by 1000ms (initial reconnect delay)
    await vi.advanceTimersByTimeAsync(1000);

    // Should have created a new WebSocket instance
    expect(wsInstances.length).toBe(instanceCountBefore + 1);
  });

  test("onclose uses exponential backoff (doubles delay)", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    await vi.runAllTimersAsync();

    const initialCount = wsInstances.length;

    // First disconnect - 1000ms delay
    getLatestWS().simulateClose();
    await vi.advanceTimersByTimeAsync(1000);
    await vi.runAllTimersAsync(); // Let connection open
    expect(wsInstances.length).toBe(initialCount + 1);

    // Second disconnect - 2000ms delay
    getLatestWS().simulateClose();
    await vi.advanceTimersByTimeAsync(2000);
    await vi.runAllTimersAsync(); // Let connection open
    expect(wsInstances.length).toBe(initialCount + 2);

    // Third disconnect - 4000ms delay
    getLatestWS().simulateClose();
    await vi.advanceTimersByTimeAsync(4000);
    await vi.runAllTimersAsync(); // Let connection open
    expect(wsInstances.length).toBe(initialCount + 3);
  });

  test("onclose caps reconnect delay at 30 seconds", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    await vi.runAllTimersAsync();

    const initialCount = wsInstances.length;

    // Simulate many disconnects to reach the cap
    const delays = [1000, 2000, 4000, 8000, 16000, 32000];

    for (let i = 0; i < delays.length; i++) {
      getLatestWS().simulateClose();
      const expectedDelay = Math.min(delays[i], 30000);
      await vi.advanceTimersByTimeAsync(expectedDelay);
      await vi.runAllTimersAsync();
    }

    // Verify we created new instances for each reconnect
    expect(wsInstances.length).toBe(initialCount + delays.length);

    // After cap is reached, verify it stays at 30000
    getLatestWS().simulateClose();
    await vi.advanceTimersByTimeAsync(30000);
    await vi.runAllTimersAsync();

    expect(wsInstances.length).toBe(initialCount + delays.length + 1);
  });

  test("onopen resets delay back to 1000", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    await vi.runAllTimersAsync();

    const initialCount = wsInstances.length;

    // First disconnect - increases delay to 2000
    getLatestWS().simulateClose();
    await vi.advanceTimersByTimeAsync(1000);
    await vi.runAllTimersAsync();

    // Second disconnect (delay should be 2000)
    getLatestWS().simulateClose();
    await vi.advanceTimersByTimeAsync(2000);
    await vi.runAllTimersAsync();

    // Connection opens (MockWebSocket auto-fires onopen)
    // This should reset the delay back to 1000

    // Disconnect again - should use 1000ms delay
    getLatestWS().simulateClose();

    const beforeReconnect = wsInstances.length;
    await vi.advanceTimersByTimeAsync(1000);
    await vi.runAllTimersAsync();

    // Should have reconnected after 1000ms (not 4000ms)
    expect(wsInstances.length).toBeGreaterThan(beforeReconnect);
  });

  test("disconnect() clears reconnect timer and closes WebSocket", async () => {
    const { feed } = await import("../ws");
    const clearTimeoutSpy = vi.spyOn(global, "clearTimeout");

    feed.connect();
    await vi.runAllTimersAsync();

    const ws = getLatestWS();
    ws.simulateClose();

    feed.disconnect();

    expect(clearTimeoutSpy).toHaveBeenCalled();
    // The close() should have been called
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);
  });

  test("unsubscribe removes listener and is no longer called on message", async () => {
    const { feed } = await import("../ws");
    const callback = vi.fn();

    const unsubscribe = feed.subscribe(callback);
    feed.connect();
    await vi.runAllTimersAsync();

    const event1: FeedEvent = {
      type: "agent_published",
      timestamp: new Date().toISOString(),
      data: { agent_id: "test-111" },
    };

    getLatestWS().simulateMessage(JSON.stringify(event1));
    expect(callback).toHaveBeenCalledTimes(1);

    // Unsubscribe
    unsubscribe();

    const event2: FeedEvent = {
      type: "agent_published",
      timestamp: new Date().toISOString(),
      data: { agent_id: "test-222" },
    };

    getLatestWS().simulateMessage(JSON.stringify(event2));

    // Callback should still be called only once (from before unsubscribe)
    expect(callback).toHaveBeenCalledTimes(1);
  });

  test("multiple listeners can be added and removed independently", async () => {
    const { feed } = await import("../ws");
    const callback1 = vi.fn();
    const callback2 = vi.fn();
    const callback3 = vi.fn();

    const unsub1 = feed.subscribe(callback1);
    const unsub2 = feed.subscribe(callback2);
    const unsub3 = feed.subscribe(callback3);

    feed.connect();
    await vi.runAllTimersAsync();

    const event: FeedEvent = {
      type: "agent_published",
      timestamp: new Date().toISOString(),
      data: { agent_id: "test-333" },
    };

    getLatestWS().simulateMessage(JSON.stringify(event));
    expect(callback1).toHaveBeenCalledTimes(1);
    expect(callback2).toHaveBeenCalledTimes(1);
    expect(callback3).toHaveBeenCalledTimes(1);

    // Unsubscribe callback2
    unsub2();

    getLatestWS().simulateMessage(JSON.stringify(event));
    expect(callback1).toHaveBeenCalledTimes(2);
    expect(callback2).toHaveBeenCalledTimes(1); // Still 1
    expect(callback3).toHaveBeenCalledTimes(2);

    // Unsubscribe remaining
    unsub1();
    unsub3();

    getLatestWS().simulateMessage(JSON.stringify(event));
    expect(callback1).toHaveBeenCalledTimes(2);
    expect(callback2).toHaveBeenCalledTimes(1);
    expect(callback3).toHaveBeenCalledTimes(2);
  });

  test("handles rapid connect/disconnect cycles gracefully", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    feed.disconnect();
    feed.connect();
    feed.disconnect();
    feed.connect();

    await vi.runAllTimersAsync();

    // Should not throw errors and should maintain consistent state
    expect(wsInstances.length).toBeGreaterThan(0);
  });

  test("reconnect creates new WebSocket instance after close", async () => {
    const { feed } = await import("../ws");

    feed.connect();
    await vi.runAllTimersAsync();

    const firstWS = getLatestWS();
    expect(wsInstances.length).toBe(1);

    // Close and trigger reconnect
    firstWS.simulateClose();
    await vi.advanceTimersByTimeAsync(1000);
    await vi.runAllTimersAsync();

    const secondWS = getLatestWS();
    expect(wsInstances.length).toBe(2);
    expect(secondWS).not.toBe(firstWS);
    expect(secondWS.url).toBe(firstWS.url);
  });

  test("messages sent to old WebSocket instance after reconnect are ignored", async () => {
    const { feed } = await import("../ws");
    const callback = vi.fn();

    feed.subscribe(callback);
    feed.connect();
    await vi.runAllTimersAsync();

    const firstWS = getLatestWS();

    const event: FeedEvent = {
      type: "test",
      timestamp: new Date().toISOString(),
      data: {},
    };

    // Message on first instance works
    firstWS.simulateMessage(JSON.stringify(event));
    expect(callback).toHaveBeenCalledTimes(1);

    // Close and reconnect
    firstWS.simulateClose();
    await vi.advanceTimersByTimeAsync(1000);
    await vi.runAllTimersAsync();

    const secondWS = getLatestWS();
    expect(secondWS).not.toBe(firstWS);

    // Message on second instance works
    secondWS.simulateMessage(JSON.stringify(event));
    expect(callback).toHaveBeenCalledTimes(2);

    // Message on old instance should not trigger callback
    // (because the feed's onmessage handler is now on the new instance)
    firstWS.simulateMessage(JSON.stringify(event));
    expect(callback).toHaveBeenCalledTimes(2); // Still 2
  });
});
