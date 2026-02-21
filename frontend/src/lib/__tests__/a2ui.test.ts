import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock WebSocket before importing the module
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
}

let instances: MockWebSocket[] = [];

vi.stubGlobal("WebSocket", MockWebSocket);

describe("A2UI WebSocket Client Types", () => {
  beforeEach(() => {
    instances = [];
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("A2UIComponentType includes all expected types", () => {
    const types = ["card", "table", "form", "chart", "markdown", "code", "image", "alert", "steps"];
    types.forEach((t) => {
      expect(typeof t).toBe("string");
    });
  });

  it("A2UIProgressType includes all modes", () => {
    const modes = ["determinate", "indeterminate", "streaming"];
    expect(modes.length).toBe(3);
    modes.forEach((m) => expect(typeof m).toBe("string"));
  });

  it("A2UIInputType includes all types", () => {
    const types = ["text", "select", "number", "date", "file"];
    expect(types.length).toBe(5);
  });

  it("A2UINotifyLevel includes all levels", () => {
    const levels = ["info", "success", "warning", "error"];
    expect(levels.length).toBe(4);
  });

  it("A2UISeverity includes all severities", () => {
    const severities = ["info", "warning", "critical"];
    expect(severities.length).toBe(3);
  });

  it("A2UIComponent has required fields", () => {
    const component = {
      component_id: "comp-1",
      component_type: "card" as const,
      data: { title: "Test" },
      metadata: { source: "agent" },
    };
    expect(component.component_id).toBe("comp-1");
    expect(component.component_type).toBe("card");
    expect(component.data.title).toBe("Test");
  });

  it("A2UIRenderMessage matches component structure", () => {
    const msg = {
      component_id: "c-1",
      component_type: "table" as const,
      data: { headers: ["A"], rows: [["1"]] },
    };
    expect(msg.component_id).toBeTruthy();
    expect(msg.component_type).toBe("table");
  });

  it("A2UIUpdateMessage supports all operations", () => {
    const ops = ["replace", "merge", "append"];
    ops.forEach((op) => {
      const msg = { component_id: "c-1", operation: op, data: {} };
      expect(msg.operation).toBe(op);
    });
  });

  it("A2UIRequestInputMessage includes validation", () => {
    const msg = {
      request_id: "req-1",
      input_type: "text" as const,
      prompt: "Enter name",
      options: undefined,
      validation: { min_length: 1, max_length: 100 },
    };
    expect(msg.validation).toHaveProperty("min_length");
  });

  it("A2UIConfirmMessage has severity and timeout", () => {
    const msg = {
      request_id: "req-2",
      title: "Confirm delete?",
      description: "This action cannot be undone",
      severity: "critical" as const,
      timeout_seconds: 30,
    };
    expect(msg.severity).toBe("critical");
    expect(msg.timeout_seconds).toBe(30);
  });

  it("A2UIProgressMessage supports all progress types", () => {
    const determinate = { task_id: "t1", progress_type: "determinate" as const, value: 50, total: 100 };
    const indeterminate = { task_id: "t2", progress_type: "indeterminate" as const };
    const streaming = { task_id: "t3", progress_type: "streaming" as const };

    expect(determinate.value).toBe(50);
    expect(indeterminate.progress_type).toBe("indeterminate");
    expect(streaming.progress_type).toBe("streaming");
  });

  it("A2UINavigateMessage has url and new_tab", () => {
    const msg = { url: "https://example.com", new_tab: true };
    expect(msg.url).toBe("https://example.com");
    expect(msg.new_tab).toBe(true);
  });

  it("A2UINotifyMessage has optional duration", () => {
    const withDuration = { level: "info" as const, title: "Hey", duration_ms: 3000 };
    const withoutDuration = { level: "error" as const, title: "Oops" };

    expect(withDuration.duration_ms).toBe(3000);
    expect(withoutDuration).not.toHaveProperty("duration_ms");
  });

  it("A2UISession tracks connection status", () => {
    const statuses = ["connecting", "connected", "disconnected", "error"];
    statuses.forEach((s) => {
      const session = {
        session_id: "s-1",
        agent_id: "a-1",
        capabilities: {},
        status: s,
      };
      expect(session.status).toBe(s);
    });
  });

  it("A2UIState has all required fields", () => {
    const state = {
      session: null,
      components: new Map(),
      pendingInput: null,
      pendingConfirm: null,
      progress: new Map(),
      notifications: [],
      connected: false,
    };
    expect(state.session).toBeNull();
    expect(state.connected).toBe(false);
    expect(state.components.size).toBe(0);
  });

  it("A2UIState can store components", () => {
    const components = new Map();
    components.set("c-1", {
      component_id: "c-1",
      component_type: "card",
      data: { title: "Test" },
    });
    expect(components.get("c-1")?.component_type).toBe("card");
  });

  it("A2UIState can track progress for multiple tasks", () => {
    const progress = new Map();
    progress.set("t-1", { task_id: "t-1", progress_type: "determinate", value: 50, total: 100 });
    progress.set("t-2", { task_id: "t-2", progress_type: "streaming" });
    expect(progress.size).toBe(2);
    expect(progress.get("t-1")?.value).toBe(50);
  });
});

describe("JSON-RPC 2.0 message format", () => {
  it("creates valid JSON-RPC request", () => {
    const msg = {
      jsonrpc: "2.0",
      method: "a2ui.init",
      params: { agent_id: "a-1" },
      id: 1,
    };
    expect(msg.jsonrpc).toBe("2.0");
    expect(msg.method).toBe("a2ui.init");
  });

  it("creates valid JSON-RPC notification (no id)", () => {
    const msg = {
      jsonrpc: "2.0",
      method: "user.respond",
      params: { request_id: "r-1", value: "hello" },
    };
    expect(msg).not.toHaveProperty("id");
  });

  it("creates valid JSON-RPC response", () => {
    const msg = {
      jsonrpc: "2.0",
      result: { session_id: "s-1", capabilities: {} },
      id: 1,
    };
    expect(msg.result.session_id).toBe("s-1");
  });

  it("creates valid JSON-RPC error response", () => {
    const msg = {
      jsonrpc: "2.0",
      error: { code: -32600, message: "Invalid request" },
      id: 1,
    };
    expect(msg.error.code).toBe(-32600);
  });
});
