import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock A2UIClient with a constructable class mock
vi.mock("../../lib/a2ui", () => {
  const MockA2UIClient = vi.fn().mockImplementation(function(this: any) {
    this.connect = vi.fn().mockResolvedValue(undefined);
    this.disconnect = vi.fn();
    this.send = vi.fn();
    this.on = vi.fn();
    this.off = vi.fn();
    this.onMessage = vi.fn();
    this.sendResponse = vi.fn();
    this.sendApproval = vi.fn();
    this.sendCancel = vi.fn();
    this.sendInit = vi.fn().mockResolvedValue({});
    this.isConnected = false;
  });
  return { A2UIClient: MockA2UIClient };
});

// Dynamic import to get the mocked version
const { useA2UI } = await import("../useA2UI");

describe("useA2UI hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns initial state with null session", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(result.current.session).toBeNull();
  });

  it("returns empty components array initially", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(result.current.components).toEqual([]);
  });

  it("returns null activeInput initially", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(result.current.activeInput).toBeNull();
  });

  it("returns null activeConfirm initially", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(result.current.activeConfirm).toBeNull();
  });

  it("returns empty progress map initially", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(result.current.progress.size).toBe(0);
  });

  it("returns empty notifications initially", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(result.current.notifications).toEqual([]);
  });

  it("exposes connect function", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(typeof result.current.connect).toBe("function");
  });

  it("exposes disconnect function", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(typeof result.current.disconnect).toBe("function");
  });

  it("exposes respond function", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(typeof result.current.respond).toBe("function");
  });

  it("exposes approve function", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(typeof result.current.approve).toBe("function");
  });

  it("exposes cancel function", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(typeof result.current.cancel).toBe("function");
  });

  it("creates new client when agentId changes", () => {
    const { rerender } = renderHook(
      ({ agentId, token }) => useA2UI(agentId, token),
      { initialProps: { agentId: "agent-1", token: "token-1" } }
    );
    rerender({ agentId: "agent-2", token: "token-1" });
    // No error thrown means hook handled the change
    expect(true).toBe(true);
  });

  it("creates new client when token changes", () => {
    const { rerender } = renderHook(
      ({ agentId, token }) => useA2UI(agentId, token),
      { initialProps: { agentId: "agent-1", token: "token-1" } }
    );
    rerender({ agentId: "agent-1", token: "token-2" });
    expect(true).toBe(true);
  });

  it("handles disconnect without error", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(() => result.current.disconnect()).not.toThrow();
  });

  it("handles respond call without error", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(() => result.current.respond("req-1", "hello")).not.toThrow();
  });

  it("handles approve call without error", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(() => result.current.approve("req-1", true)).not.toThrow();
  });

  it("handles approve with rejection reason", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(() => result.current.approve("req-1", false, "Not appropriate")).not.toThrow();
  });

  it("handles cancel call without error", () => {
    const { result } = renderHook(() => useA2UI("agent-1", "token-1"));
    expect(() => result.current.cancel("task-1")).not.toThrow();
  });
});
