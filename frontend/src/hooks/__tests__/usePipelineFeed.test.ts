import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
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

describe("usePipelineFeed", () => {
  let capturedCallback: ((event: FeedEvent) => void) | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
    capturedCallback = undefined;

    mockSubscribe.mockImplementation((callback: (event: FeedEvent) => void) => {
      capturedCallback = callback;
      return vi.fn();
    });
  });

  afterEach(() => {
    capturedCallback = undefined;
  });

  // Helper to create a FeedEvent
  function makeEvent(
    type: string,
    extras: Record<string, unknown> = {},
  ): FeedEvent {
    return {
      type,
      timestamp: new Date().toISOString(),
      data: { ...extras },
      ...extras,
    };
  }

  test("returns initial empty state", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    expect(result.current.executions).toEqual([]);
    expect(result.current.liveEvents).toEqual([]);
    expect(result.current.totalSteps).toBe(0);
  });

  test("connects to WebSocket on mount", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    renderHook(() => usePipelineFeed());

    expect(mockConnect).toHaveBeenCalledTimes(1);
  });

  test("subscribes to feed events on mount", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    renderHook(() => usePipelineFeed());

    expect(mockSubscribe).toHaveBeenCalledTimes(1);
    expect(mockSubscribe).toHaveBeenCalledWith(expect.any(Function));
  });

  test("handles incoming pipeline events and updates liveEvents", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event = makeEvent("agent_published", { agent_id: "agent-1", agent_name: "Agent One" });

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      expect(result.current.liveEvents).toHaveLength(1);
      expect(result.current.liveEvents[0]).toEqual(event);
    });
  });

  test("updates executions state when events arrive", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event = makeEvent("agent_published", { agent_id: "agent-1", agent_name: "Agent One" });

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(1);
      const exec = result.current.executions[0];
      expect(exec.agentId).toBe("agent-1");
      expect(exec.agentName).toBe("Agent One");
      expect(exec.status).toBe("active");
      expect(exec.steps).toHaveLength(1);
      expect(exec.steps[0].action).toBe("agent published");
      expect(exec.steps[0].status).toBe("completed");
    });
  });

  test("accumulates steps for the same agent across multiple events", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event1 = makeEvent("agent_published", { agent_id: "agent-1", agent_name: "Agent One" });
    const event2 = makeEvent("agent_purchased", { agent_id: "agent-1", agent_name: "Agent One" });

    act(() => {
      capturedCallback?.(event1);
      capturedCallback?.(event2);
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(1);
      const exec = result.current.executions[0];
      expect(exec.steps).toHaveLength(2);
      expect(exec.steps[0].action).toBe("agent published");
      expect(exec.steps[1].action).toBe("agent purchased");
    });
  });

  test("creates separate executions for different agents", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event1 = makeEvent("agent_published", { agent_id: "agent-1", agent_name: "Agent One" });
    const event2 = makeEvent("agent_published", { agent_id: "agent-2", agent_name: "Agent Two" });

    act(() => {
      capturedCallback?.(event1);
      capturedCallback?.(event2);
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(2);
      const ids = result.current.executions.map((e) => e.agentId);
      expect(ids).toContain("agent-1");
      expect(ids).toContain("agent-2");
    });
  });

  test("cleans up subscription on unmount", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const mockUnsubscribe = vi.fn();
    mockSubscribe.mockReturnValue(mockUnsubscribe);

    const { unmount } = renderHook(() => usePipelineFeed());

    expect(mockUnsubscribe).not.toHaveBeenCalled();

    unmount();

    expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
  });

  test("uses seller_id as agent ID fallback when agent_id is missing", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event = makeEvent("sale_completed", { seller_id: "seller-99" });

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(1);
      expect(result.current.executions[0].agentId).toBe("seller-99");
    });
  });

  test("uses buyer_id as agent ID fallback when agent_id and seller_id are missing", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event = makeEvent("purchase_completed", { buyer_id: "buyer-42" });

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(1);
      expect(result.current.executions[0].agentId).toBe("buyer-42");
    });
  });

  test("defaults agent ID to 'unknown' when no ID fields are present", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event: FeedEvent = {
      type: "system_event",
      timestamp: new Date().toISOString(),
      data: { some_field: "value" },
    };

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(1);
      expect(result.current.executions[0].agentId).toBe("unknown");
      expect(result.current.executions[0].agentName).toBe("unknown");
    });
  });

  test("handles multiple rapid events preserving order (newest first in liveEvents)", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const events = Array.from({ length: 10 }, (_, i) =>
      makeEvent("rapid_event", { agent_id: `agent-${i}`, index: i }),
    );

    act(() => {
      events.forEach((e) => capturedCallback?.(e));
    });

    await waitFor(() => {
      expect(result.current.liveEvents).toHaveLength(10);
      // Most recent event first
      expect((result.current.liveEvents[0] as unknown as Record<string, unknown>).agent_id).toBe("agent-9");
      // Oldest event last
      expect((result.current.liveEvents[9] as unknown as Record<string, unknown>).agent_id).toBe("agent-0");
    });
  });

  test("caps liveEvents at 100 entries", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    act(() => {
      for (let i = 0; i < 120; i++) {
        capturedCallback?.(makeEvent("bulk_event", { agent_id: `a-${i}`, index: i }));
      }
    });

    await waitFor(() => {
      expect(result.current.liveEvents).toHaveLength(100);
      // Most recent event is first (index 119)
      expect((result.current.liveEvents[0] as unknown as Record<string, unknown>).agent_id).toBe("a-119");
    });
  });

  test("caps steps per agent execution at 50", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    act(() => {
      for (let i = 0; i < 60; i++) {
        capturedCallback?.(makeEvent(`action_${i}`, { agent_id: "agent-1", agent_name: "Agent One" }));
      }
    });

    await waitFor(() => {
      expect(result.current.executions).toHaveLength(1);
      expect(result.current.executions[0].steps).toHaveLength(50);
      // Should keep the most recent 50 steps (actions 10-59 since 0-9 are dropped)
      expect(result.current.executions[0].steps[49].action).toBe("action 59");
    });
  });

  test("returns correct event types via toolCall.name", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event = makeEvent("agent_tool_invoked", { agent_id: "agent-1" });

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      const step = result.current.executions[0].steps[0];
      expect(step.toolCall).toBeDefined();
      expect(step.toolCall!.name).toBe("agent_tool_invoked");
      expect(step.action).toBe("agent tool invoked");
    });
  });

  test("tracks totalSteps counter across all events", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    act(() => {
      capturedCallback?.(makeEvent("event_a", { agent_id: "a" }));
      capturedCallback?.(makeEvent("event_b", { agent_id: "b" }));
      capturedCallback?.(makeEvent("event_c", { agent_id: "a" }));
    });

    await waitFor(() => {
      expect(result.current.totalSteps).toBeGreaterThanOrEqual(3);
    });
  });

  test("callback is called with correct data and sets delivery_ms as latencyMs", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { result } = renderHook(() => usePipelineFeed());

    const event = makeEvent("agent_published", {
      agent_id: "agent-1",
      agent_name: "Fast Agent",
      delivery_ms: 42,
    });

    act(() => {
      capturedCallback?.(event);
    });

    await waitFor(() => {
      const step = result.current.executions[0].steps[0];
      expect(step.latencyMs).toBe(42);
      expect(step.agentName).toBe("Fast Agent");
    });
  });

  test("does not re-connect on re-render", async () => {
    const { usePipelineFeed } = await import("../usePipelineFeed");

    const { rerender } = renderHook(() => usePipelineFeed());

    expect(mockConnect).toHaveBeenCalledTimes(1);

    rerender();
    rerender();
    rerender();

    expect(mockConnect).toHaveBeenCalledTimes(1);
  });
});
