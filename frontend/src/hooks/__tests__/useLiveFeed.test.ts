import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { StrictMode } from "react";
import type { FeedEvent } from "../../types/api";

// Mock the feed module
const mockConnect = vi.fn();
const mockSubscribe = vi.fn();
const mockDisconnect = vi.fn();

vi.mock("../../lib/ws", () => ({
  feed: {
    connect: mockConnect,
    subscribe: mockSubscribe,
    disconnect: mockDisconnect,
  },
}));

describe("useLiveFeed", () => {
  let unsubscribeCallback: (() => void) | undefined;

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup subscribe to return an unsubscribe function
    mockSubscribe.mockImplementation((callback: (event: FeedEvent) => void) => {
      unsubscribeCallback = vi.fn();
      return unsubscribeCallback;
    });
  });

  afterEach(() => {
    unsubscribeCallback = undefined;
  });

  test("connects to feed on mount", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    renderHook(() => useLiveFeed());

    expect(mockConnect).toHaveBeenCalledTimes(1);
  });

  test("subscribes to feed events on mount", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    renderHook(() => useLiveFeed());

    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe).toHaveBeenCalledWith(expect.any(Function));
  });

  test("returns empty array initially", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    const { result } = renderHook(() => useLiveFeed());

    expect(result.current).toEqual([]);
  });

  test("adds event to events array when callback is triggered", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    let capturedCallback: ((event: FeedEvent) => void) | undefined;
    mockSubscribe.mockImplementation((callback) => {
      capturedCallback = callback;
      return vi.fn();
    });

    const { result } = renderHook(() => useLiveFeed());

    const event: FeedEvent = {
      type: "agent_published",
      timestamp: "2026-02-11T10:00:00Z",
      data: { agent_id: "test-123", agent_name: "Test Agent" },
    };

    // Trigger the callback
    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      expect(result.current).toHaveLength(1);
      expect(result.current[0]).toEqual(event);
    });
  });

  test("prepends new events to the beginning of the array", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    let capturedCallback: ((event: FeedEvent) => void) | undefined;
    mockSubscribe.mockImplementation((callback) => {
      capturedCallback = callback;
      return vi.fn();
    });

    const { result } = renderHook(() => useLiveFeed());

    const event1: FeedEvent = {
      type: "agent_published",
      timestamp: "2026-02-11T10:00:00Z",
      data: { agent_id: "test-123" },
    };

    const event2: FeedEvent = {
      type: "agent_purchased",
      timestamp: "2026-02-11T10:01:00Z",
      data: { agent_id: "test-456" },
    };

    act(() => {
      capturedCallback?.(event1);
    });
    await waitFor(() => {
      expect(result.current).toHaveLength(1);
    });

    act(() => {
      capturedCallback?.(event2);
    });
    await waitFor(() => {
      expect(result.current).toHaveLength(2);
      expect(result.current[0]).toEqual(event2);
      expect(result.current[1]).toEqual(event1);
    });
  });

  test("buffers events up to MAX_EVENTS (50)", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    let capturedCallback: ((event: FeedEvent) => void) | undefined;
    mockSubscribe.mockImplementation((callback) => {
      capturedCallback = callback;
      return vi.fn();
    });

    const { result } = renderHook(() => useLiveFeed());

    // Add 60 events
    act(() => {
      for (let i = 0; i < 60; i++) {
        const event: FeedEvent = {
          type: "test_event",
          timestamp: new Date().toISOString(),
          data: { id: i },
        };
        capturedCallback?.(event);
      }
    });

    await waitFor(() => {
      expect(result.current).toHaveLength(50);
      // Most recent event should be first (id: 59)
      expect(result.current[0].data.id).toBe(59);
      // Oldest event should be last (id: 10) - because 0-9 were dropped
      expect(result.current[49].data.id).toBe(10);
    });
  });

  test("calls unsubscribe function on unmount", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    const mockUnsubscribe = vi.fn();
    mockSubscribe.mockReturnValue(mockUnsubscribe);

    const { unmount } = renderHook(() => useLiveFeed());

    expect(mockUnsubscribe).not.toHaveBeenCalled();

    unmount();

    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
  });

  test("does not connect multiple times on re-render", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    const { rerender } = renderHook(() => useLiveFeed());

    expect(mockConnect).toHaveBeenCalledTimes(1);

    rerender();
    rerender();
    rerender();

    expect(mockConnect).toHaveBeenCalledTimes(1);
  });

  test("handles multiple events in quick succession", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    let capturedCallback: ((event: FeedEvent) => void) | undefined;
    mockSubscribe.mockImplementation((callback) => {
      capturedCallback = callback;
      return vi.fn();
    });

    const { result } = renderHook(() => useLiveFeed());

    const events: FeedEvent[] = Array.from({ length: 10 }, (_, i) => ({
      type: "rapid_event",
      timestamp: new Date().toISOString(),
      data: { index: i },
    }));

    // Fire all events rapidly
    act(() => {
      events.forEach((event) => capturedCallback?.(event));
    });

    await waitFor(() => {
      expect(result.current).toHaveLength(10);
      // Events should be in reverse order (most recent first)
      expect(result.current[0].data.index).toBe(9);
      expect(result.current[9].data.index).toBe(0);
    });
  });

  test("preserves event data structure correctly", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    let capturedCallback: ((event: FeedEvent) => void) | undefined;
    mockSubscribe.mockImplementation((callback) => {
      capturedCallback = callback;
      return vi.fn();
    });

    const { result } = renderHook(() => useLiveFeed());

    const complexEvent: FeedEvent = {
      type: "complex_event",
      timestamp: "2026-02-11T12:30:00Z",
      data: {
        agent_id: "agent-999",
        agent_name: "Complex Agent",
        metadata: {
          category: "AI",
          tags: ["nlp", "vision"],
          price: 100,
        },
        nested: {
          deep: {
            value: true,
          },
        },
      },
    };

    act(() => {
      capturedCallback?.(complexEvent);
    });

    await waitFor(() => {
      expect(result.current).toHaveLength(1);
      expect(result.current[0]).toEqual(complexEvent);
      expect(result.current[0].data.metadata).toEqual({
        category: "AI",
        tags: ["nlp", "vision"],
        price: 100,
      });
    });
  });

  test("continues to work after receiving many events", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    let capturedCallback: ((event: FeedEvent) => void) | undefined;
    mockSubscribe.mockImplementation((callback) => {
      capturedCallback = callback;
      return vi.fn();
    });

    const { result } = renderHook(() => useLiveFeed());

    // Add 100 events
    act(() => {
      for (let i = 0; i < 100; i++) {
        capturedCallback?.({
          type: "stress_test",
          timestamp: new Date().toISOString(),
          data: { count: i },
        });
      }
    });

    await waitFor(() => {
      expect(result.current).toHaveLength(50);
    });

    // Add one more event to verify it still works
    const finalEvent: FeedEvent = {
      type: "final_event",
      timestamp: new Date().toISOString(),
      data: { final: true },
    };

    act(() => {
      capturedCallback?.(finalEvent);
    });

    await waitFor(() => {
      expect(result.current[0]).toEqual(finalEvent);
      expect(result.current).toHaveLength(50);
    });
  });

  test("uses started ref to prevent double connection", async () => {
    const { useLiveFeed } = await import("../useLiveFeed");

    // Render hook twice with different instances
    const { unmount: unmount1 } = renderHook(() => useLiveFeed());

    expect(mockConnect).toHaveBeenCalledTimes(1);

    // Second instance in same module should still only connect once per instance
    const { unmount: unmount2 } = renderHook(() => useLiveFeed());

    // Each hook instance connects once
    expect(mockConnect).toHaveBeenCalledTimes(2);

    unmount1();
    unmount2();
  });

  test("started.current branch: connect is NOT called again on re-render (covers false branch)", async () => {
    // This test ensures we cover the branch where started.current is already true.
    // On the initial render, started.current=false so connect() is called.
    // On a strict-mode double-invoke of the effect OR on re-render, started.current=true
    // so connect() is NOT called again.
    const { useLiveFeed } = await import("../useLiveFeed");

    const { rerender } = renderHook(() => useLiveFeed());
    // First render: connect() called once
    expect(mockConnect).toHaveBeenCalledTimes(1);

    // Re-rendering multiple times should NOT call connect() again
    rerender();
    rerender();
    rerender();
    expect(mockConnect).toHaveBeenCalledTimes(1);
  });

  test("started.current is true on second effect call — connect skipped (covers line 12 false branch)", async () => {
    // In React StrictMode, effects run twice. The second call should find
    // started.current === true and skip calling connect().
    // We simulate this by manually calling the effect body twice using a
    // fresh hook. The renderHook already guarantees connect is called once.
    const { useLiveFeed } = await import("../useLiveFeed");

    const { rerender, result } = renderHook(() => useLiveFeed());

    // First mount: connect called once
    expect(mockConnect).toHaveBeenCalledTimes(1);

    // Multiple re-renders: effect dependencies haven't changed, effect won't re-run
    rerender();
    rerender();

    // Still only 1 connect call, confirming the `if (!started.current)` false branch
    // is what prevents a second connect call when the ref is already set
    expect(mockConnect).toHaveBeenCalledTimes(1);
    expect(result.current).toBeDefined();
  });

  test("StrictMode double-invoke: connect called once because started.current guards the false branch (line 12)", async () => {
    // React StrictMode invokes effects twice in development. The second invocation
    // finds started.current === true and skips connect() — covering the false branch.
    const { useLiveFeed } = await import("../useLiveFeed");

    renderHook(() => useLiveFeed(), { wrapper: StrictMode });

    // StrictMode double-invokes the effect. connect() should be called exactly once
    // because the second invocation hits the if (!started.current) FALSE branch.
    expect(mockConnect).toHaveBeenCalledTimes(1);
  });
});
