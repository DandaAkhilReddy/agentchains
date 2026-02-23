import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// ---------------------------------------------------------------------------
// We capture the `on()` handlers that useA2UI registers so we can invoke
// them from tests.  We also capture calls to convenience methods.
// ---------------------------------------------------------------------------

let capturedHandlers: Map<string, (params: any) => void>;
let mockClientInstance: any;

vi.mock("../../lib/a2ui", () => {
  const MockA2UIClient = vi.fn().mockImplementation(function (this: any) {
    capturedHandlers = new Map();
    mockClientInstance = this;

    this.connect = vi.fn().mockResolvedValue(undefined);
    this.disconnect = vi.fn();
    this.send = vi.fn().mockReturnValue("req_1");
    this.on = vi.fn().mockImplementation((method: string, handler: (p: any) => void) => {
      capturedHandlers.set(method, handler);
    });
    this.onMessage = vi.fn();
    this.sendResponse = vi.fn();
    this.sendApproval = vi.fn();
    this.sendCancel = vi.fn();
    this.sendInit = vi.fn().mockResolvedValue({
      session_id: "s-1",
      agent_id: "agent-1",
      capabilities: {},
      status: "connected",
    });
  });
  return { A2UIClient: MockA2UIClient };
});

// Import after mock is set up
const { useA2UI } = await import("../useA2UI");

// ---------------------------------------------------------------------------
// Helper: trigger a handler that was registered via client.on()
// ---------------------------------------------------------------------------
function triggerHandler(method: string, params: any): void {
  const handler = capturedHandlers.get(method);
  if (!handler) throw new Error(`No handler registered for "${method}"`);
  handler(params);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useA2UI hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // -----------------------------------------------------------------------
  // Initial state
  // -----------------------------------------------------------------------

  describe("initial state", () => {
    it("session is null", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
      expect(result.current.session).toBeNull();
    });

    it("components is an empty array", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
      expect(result.current.components).toEqual([]);
    });

    it("activeInput is null", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
      expect(result.current.activeInput).toBeNull();
    });

    it("activeConfirm is null", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
      expect(result.current.activeConfirm).toBeNull();
    });

    it("progress map is empty", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
      expect(result.current.progress.size).toBe(0);
    });

    it("notifications is empty", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
      expect(result.current.notifications).toEqual([]);
    });
  });

  // -----------------------------------------------------------------------
  // Client lifecycle
  // -----------------------------------------------------------------------

  describe("client lifecycle", () => {
    it("registers handlers for all A2UI methods on mount", () => {
      renderHook(() => useA2UI("agent-1", "token-1"));
      expect(capturedHandlers.has("ui.render")).toBe(true);
      expect(capturedHandlers.has("ui.update")).toBe(true);
      expect(capturedHandlers.has("ui.request_input")).toBe(true);
      expect(capturedHandlers.has("ui.confirm")).toBe(true);
      expect(capturedHandlers.has("ui.progress")).toBe(true);
      expect(capturedHandlers.has("ui.navigate")).toBe(true);
      expect(capturedHandlers.has("ui.notify")).toBe(true);
    });

    it("disconnects and recreates client when agentId changes", () => {
      const { rerender } = renderHook(
        ({ agentId, token }) => useA2UI(agentId, token),
        { initialProps: { agentId: "agent-1", token: "token-1" } },
      );

      const firstClient = mockClientInstance;
      rerender({ agentId: "agent-2", token: "token-1" });

      // The cleanup of the first effect should have called disconnect
      expect(firstClient.disconnect).toHaveBeenCalled();
    });

    it("disconnects and recreates client when token changes", () => {
      const { rerender } = renderHook(
        ({ agentId, token }) => useA2UI(agentId, token),
        { initialProps: { agentId: "agent-1", token: "token-1" } },
      );

      const firstClient = mockClientInstance;
      rerender({ agentId: "agent-1", token: "token-2" });
      expect(firstClient.disconnect).toHaveBeenCalled();
    });

    it("disconnects on unmount", () => {
      const { unmount } = renderHook(() => useA2UI("agent-1", "token-1"));
      const clientInst = mockClientInstance;
      unmount();
      expect(clientInst.disconnect).toHaveBeenCalled();
    });
  });

  // -----------------------------------------------------------------------
  // connect()
  // -----------------------------------------------------------------------

  describe("connect()", () => {
    it("calls client.connect() and sendInit()", async () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      await act(async () => {
        await result.current.connect();
      });

      expect(mockClientInstance.connect).toHaveBeenCalled();
      expect(mockClientInstance.sendInit).toHaveBeenCalledWith({ agent_id: "agent-1" });
    });

    it("sets session with status connected", async () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      await act(async () => {
        await result.current.connect();
      });

      expect(result.current.session).not.toBeNull();
      expect(result.current.session!.status).toBe("connected");
    });

    it("is a no-op when clientRef is null (edge case)", async () => {
      const { result, unmount } = renderHook(() => useA2UI("agent-1", "token-1"));

      // Capture the connect callback, then unmount to clear the ref
      const connectFn = result.current.connect;
      unmount();

      // Should not throw
      await act(async () => {
        await connectFn();
      });
    });
  });

  // -----------------------------------------------------------------------
  // disconnect()
  // -----------------------------------------------------------------------

  describe("disconnect()", () => {
    it("calls client.disconnect()", async () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      await act(async () => {
        await result.current.connect();
      });

      act(() => {
        result.current.disconnect();
      });

      expect(mockClientInstance.disconnect).toHaveBeenCalled();
    });

    it("sets session status to disconnected", async () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      await act(async () => {
        await result.current.connect();
      });

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.session!.status).toBe("disconnected");
    });

    it("returns null session when there is no previous session", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.session).toBeNull();
    });
  });

  // -----------------------------------------------------------------------
  // respond()
  // -----------------------------------------------------------------------

  describe("respond()", () => {
    it("calls client.sendResponse() and clears activeInput", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      // Simulate an input request
      act(() => {
        triggerHandler("ui.request_input", {
          request_id: "req-1",
          input_type: "text",
          prompt: "Enter name",
        });
      });

      expect(result.current.activeInput).not.toBeNull();

      act(() => {
        result.current.respond("req-1", "Alice");
      });

      expect(mockClientInstance.sendResponse).toHaveBeenCalledWith("req-1", "Alice");
      expect(result.current.activeInput).toBeNull();
    });
  });

  // -----------------------------------------------------------------------
  // approve()
  // -----------------------------------------------------------------------

  describe("approve()", () => {
    it("calls client.sendApproval() and clears activeConfirm", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.confirm", {
          request_id: "req-2",
          title: "Confirm?",
          description: "Are you sure?",
          severity: "warning",
        });
      });

      expect(result.current.activeConfirm).not.toBeNull();

      act(() => {
        result.current.approve("req-2", true);
      });

      expect(mockClientInstance.sendApproval).toHaveBeenCalledWith("req-2", true, undefined);
      expect(result.current.activeConfirm).toBeNull();
    });

    it("passes rejection reason", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.confirm", {
          request_id: "req-3",
          title: "Delete?",
          description: "This is permanent",
          severity: "critical",
        });
      });

      act(() => {
        result.current.approve("req-3", false, "Not authorized");
      });

      expect(mockClientInstance.sendApproval).toHaveBeenCalledWith("req-3", false, "Not authorized");
    });
  });

  // -----------------------------------------------------------------------
  // cancel()
  // -----------------------------------------------------------------------

  describe("cancel()", () => {
    it("calls client.sendCancel()", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        result.current.cancel("task-42");
      });

      expect(mockClientInstance.sendCancel).toHaveBeenCalledWith("task-42");
    });
  });

  // -----------------------------------------------------------------------
  // ui.render handler
  // -----------------------------------------------------------------------

  describe("ui.render handler", () => {
    it("adds a new component to the components array", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "Hello" },
          metadata: { source: "agent" },
        });
      });

      expect(result.current.components).toHaveLength(1);
      expect(result.current.components[0]).toEqual({
        component_id: "c-1",
        component_type: "card",
        data: { title: "Hello" },
        metadata: { source: "agent" },
      });
    });

    it("replaces a component with the same id", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "V1" },
        });
      });

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "table",
          data: { title: "V2" },
        });
      });

      expect(result.current.components).toHaveLength(1);
      expect(result.current.components[0].component_type).toBe("table");
      expect(result.current.components[0].data.title).toBe("V2");
    });

    it("handles multiple components", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: {},
        });
      });

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-2",
          component_type: "table",
          data: {},
        });
      });

      expect(result.current.components).toHaveLength(2);
    });
  });

  // -----------------------------------------------------------------------
  // ui.update handler
  // -----------------------------------------------------------------------

  describe("ui.update handler", () => {
    it("replace operation: replaces data entirely", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "Old", subtitle: "Keep" },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "replace",
          data: { title: "New" },
        });
      });

      expect(result.current.components[0].data).toEqual({ title: "New" });
    });

    it("merge operation: merges data with existing", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "Hello", count: 1 },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "merge",
          data: { count: 2, extra: true },
        });
      });

      expect(result.current.components[0].data).toEqual({
        title: "Hello",
        count: 2,
        extra: true,
      });
    });

    it("append operation: concatenates arrays", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "table",
          data: { rows: [["a"], ["b"]] },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "append",
          data: { rows: [["c"]] },
        });
      });

      expect(result.current.components[0].data.rows).toEqual([["a"], ["b"], ["c"]]);
    });

    it("append operation: concatenates strings", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "markdown",
          data: { content: "Hello " },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "append",
          data: { content: "World" },
        });
      });

      expect(result.current.components[0].data.content).toBe("Hello World");
    });

    it("append operation: falls back to overwrite for non-array, non-string", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { count: 10 },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "append",
          data: { count: 20 },
        });
      });

      expect(result.current.components[0].data.count).toBe(20);
    });

    it("default operation (unknown): uses data as-is", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "Old" },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "unknown_op",
          data: { title: "Fallback" },
        });
      });

      expect(result.current.components[0].data).toEqual({ title: "Fallback" });
    });

    it("ignores update for non-existent component", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.update", {
          component_id: "does-not-exist",
          operation: "replace",
          data: { title: "Ghost" },
        });
      });

      expect(result.current.components).toEqual([]);
    });

    it("preserves component_type and other fields on update", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "Old" },
          metadata: { source: "agent" },
        });
      });

      act(() => {
        triggerHandler("ui.update", {
          component_id: "c-1",
          operation: "replace",
          data: { title: "New" },
        });
      });

      expect(result.current.components[0].component_type).toBe("card");
      expect(result.current.components[0].metadata).toEqual({ source: "agent" });
    });
  });

  // -----------------------------------------------------------------------
  // ui.request_input handler
  // -----------------------------------------------------------------------

  describe("ui.request_input handler", () => {
    it("sets activeInput", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.request_input", {
          request_id: "req-1",
          input_type: "text",
          prompt: "What is your name?",
        });
      });

      expect(result.current.activeInput).toEqual({
        request_id: "req-1",
        input_type: "text",
        prompt: "What is your name?",
      });
    });

    it("replaces previous activeInput on new request", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.request_input", {
          request_id: "req-1",
          input_type: "text",
          prompt: "First",
        });
      });

      act(() => {
        triggerHandler("ui.request_input", {
          request_id: "req-2",
          input_type: "select",
          prompt: "Second",
          options: ["a", "b"],
        });
      });

      expect(result.current.activeInput!.request_id).toBe("req-2");
    });
  });

  // -----------------------------------------------------------------------
  // ui.confirm handler
  // -----------------------------------------------------------------------

  describe("ui.confirm handler", () => {
    it("sets activeConfirm", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.confirm", {
          request_id: "req-5",
          title: "Delete?",
          description: "This is permanent",
          severity: "critical",
          timeout_seconds: 30,
        });
      });

      expect(result.current.activeConfirm).toEqual({
        request_id: "req-5",
        title: "Delete?",
        description: "This is permanent",
        severity: "critical",
        timeout_seconds: 30,
      });
    });
  });

  // -----------------------------------------------------------------------
  // ui.progress handler
  // -----------------------------------------------------------------------

  describe("ui.progress handler", () => {
    it("adds progress entry keyed by task_id", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.progress", {
          task_id: "t-1",
          progress_type: "determinate",
          value: 50,
          total: 100,
          message: "Half done",
        });
      });

      expect(result.current.progress.size).toBe(1);
      expect(result.current.progress.get("t-1")).toEqual({
        task_id: "t-1",
        progress_type: "determinate",
        value: 50,
        total: 100,
        message: "Half done",
      });
    });

    it("updates existing progress entry", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.progress", {
          task_id: "t-1",
          progress_type: "determinate",
          value: 10,
          total: 100,
        });
      });

      act(() => {
        triggerHandler("ui.progress", {
          task_id: "t-1",
          progress_type: "determinate",
          value: 90,
          total: 100,
        });
      });

      expect(result.current.progress.get("t-1")!.value).toBe(90);
    });

    it("tracks multiple concurrent tasks", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.progress", {
          task_id: "t-1",
          progress_type: "indeterminate",
        });
      });

      act(() => {
        triggerHandler("ui.progress", {
          task_id: "t-2",
          progress_type: "streaming",
        });
      });

      expect(result.current.progress.size).toBe(2);
    });
  });

  // -----------------------------------------------------------------------
  // ui.navigate handler
  // -----------------------------------------------------------------------

  describe("ui.navigate handler", () => {
    let openSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
      openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    });

    afterEach(() => {
      openSpy.mockRestore();
    });

    it("opens URL in new tab when new_tab is true", () => {
      renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.navigate", {
          url: "https://example.com",
          new_tab: true,
        });
      });

      expect(openSpy).toHaveBeenCalledWith(
        "https://example.com",
        "_blank",
        "noopener,noreferrer",
      );
    });

    it("navigates in current tab when new_tab is false", () => {
      // We cannot easily test setting window.location.href in jsdom
      // because it triggers navigation. We use a property spy instead.
      const hrefSetter = vi.fn();
      Object.defineProperty(window, "location", {
        value: {
          ...window.location,
          href: "",
          protocol: "http:",
          host: "localhost",
        },
        writable: true,
      });
      Object.defineProperty(window.location, "href", {
        set: hrefSetter,
        get: () => "",
      });

      renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.navigate", {
          url: "https://example.com/page",
          new_tab: false,
        });
      });

      expect(hrefSetter).toHaveBeenCalledWith("https://example.com/page");
    });
  });

  // -----------------------------------------------------------------------
  // ui.notify handler
  // -----------------------------------------------------------------------

  describe("ui.notify handler", () => {
    it("adds notification to the list", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", {
          level: "info",
          title: "Hello",
          message: "World",
        });
      });

      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].title).toBe("Hello");
    });

    it("auto-dismisses after duration_ms", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", {
          level: "success",
          title: "Done",
          duration_ms: 3000,
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(3000);
      });

      expect(result.current.notifications).toHaveLength(0);
    });

    it("uses default 5000ms when duration_ms is not provided", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", {
          level: "info",
          title: "Default timer",
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(4999);
      });
      expect(result.current.notifications).toHaveLength(1);

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(result.current.notifications).toHaveLength(0);
    });

    it("does not auto-dismiss when duration_ms is 0", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", {
          level: "error",
          title: "Persistent",
          duration_ms: 0,
        });
      });

      act(() => {
        vi.advanceTimersByTime(60_000);
      });

      expect(result.current.notifications).toHaveLength(1);
    });

    it("does not auto-dismiss when duration_ms is negative", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", {
          level: "warning",
          title: "Sticky",
          duration_ms: -1,
        });
      });

      act(() => {
        vi.advanceTimersByTime(60_000);
      });

      expect(result.current.notifications).toHaveLength(1);
    });

    it("accumulates multiple notifications", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", { level: "info", title: "N1", duration_ms: 0 });
      });
      act(() => {
        triggerHandler("ui.notify", { level: "info", title: "N2", duration_ms: 0 });
      });
      act(() => {
        triggerHandler("ui.notify", { level: "info", title: "N3", duration_ms: 0 });
      });

      expect(result.current.notifications).toHaveLength(3);
    });

    it("removes only the specific notification on auto-dismiss", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.notify", {
          level: "info",
          title: "Short",
          duration_ms: 1000,
        });
      });

      act(() => {
        triggerHandler("ui.notify", {
          level: "error",
          title: "Persistent",
          duration_ms: 0,
        });
      });

      expect(result.current.notifications).toHaveLength(2);

      act(() => {
        vi.advanceTimersByTime(1000);
      });

      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].title).toBe("Persistent");
    });
  });

  // -----------------------------------------------------------------------
  // components derived array
  // -----------------------------------------------------------------------

  describe("components array", () => {
    it("is derived from the internal componentsMap", () => {
      const { result } = renderHook(() => useA2UI("agent-1", "token-1"));

      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-1",
          component_type: "card",
          data: { title: "A" },
        });
      });
      act(() => {
        triggerHandler("ui.render", {
          component_id: "c-2",
          component_type: "table",
          data: { title: "B" },
        });
      });

      expect(result.current.components).toHaveLength(2);
      const ids = result.current.components.map((c) => c.component_id);
      expect(ids).toContain("c-1");
      expect(ids).toContain("c-2");
    });
  });
});
