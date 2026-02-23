import { describe, it, expect } from "vitest";
import type {
  A2UIComponentType,
  A2UIProgressType,
  A2UIInputType,
  A2UINotifyLevel,
  A2UISeverity,
  A2UIComponent,
  A2UIRenderMessage,
  A2UIUpdateMessage,
  A2UIRequestInputMessage,
  A2UIInputRequest,
  A2UIConfirmMessage,
  A2UIConfirmRequest,
  A2UIProgressMessage,
  A2UIProgress,
  A2UINavigateMessage,
  A2UINotifyMessage,
  A2UINotification,
  A2UISession,
  A2UIState,
} from "../a2ui";

// ── A2UIComponentType ──────────────────────────────────────────────────────

describe("A2UIComponentType", () => {
  it("accepts all valid component type string literals", () => {
    const types: A2UIComponentType[] = [
      "card",
      "table",
      "form",
      "chart",
      "markdown",
      "code",
      "image",
      "alert",
      "steps",
    ];
    expect(types).toHaveLength(9);
    types.forEach((t) => expect(typeof t).toBe("string"));
  });

  it("card is a valid A2UIComponentType", () => {
    const t: A2UIComponentType = "card";
    expect(t).toBe("card");
  });

  it("table is a valid A2UIComponentType", () => {
    const t: A2UIComponentType = "table";
    expect(t).toBe("table");
  });

  it("steps is a valid A2UIComponentType", () => {
    const t: A2UIComponentType = "steps";
    expect(t).toBe("steps");
  });
});

// ── A2UIProgressType ───────────────────────────────────────────────────────

describe("A2UIProgressType", () => {
  it("accepts all three progress mode literals", () => {
    const modes: A2UIProgressType[] = [
      "determinate",
      "indeterminate",
      "streaming",
    ];
    expect(modes).toHaveLength(3);
  });

  it("determinate is a valid progress type", () => {
    const m: A2UIProgressType = "determinate";
    expect(m).toBe("determinate");
  });

  it("streaming is a valid progress type", () => {
    const m: A2UIProgressType = "streaming";
    expect(m).toBe("streaming");
  });
});

// ── A2UIInputType ──────────────────────────────────────────────────────────

describe("A2UIInputType", () => {
  it("accepts all five input type literals", () => {
    const types: A2UIInputType[] = [
      "text",
      "select",
      "number",
      "date",
      "file",
    ];
    expect(types).toHaveLength(5);
  });

  it("text is a valid input type", () => {
    const t: A2UIInputType = "text";
    expect(t).toBe("text");
  });

  it("file is a valid input type", () => {
    const t: A2UIInputType = "file";
    expect(t).toBe("file");
  });
});

// ── A2UINotifyLevel ────────────────────────────────────────────────────────

describe("A2UINotifyLevel", () => {
  it("accepts all four notification severity levels", () => {
    const levels: A2UINotifyLevel[] = [
      "info",
      "success",
      "warning",
      "error",
    ];
    expect(levels).toHaveLength(4);
  });

  it("success is a valid notify level", () => {
    const l: A2UINotifyLevel = "success";
    expect(l).toBe("success");
  });

  it("error is a valid notify level", () => {
    const l: A2UINotifyLevel = "error";
    expect(l).toBe("error");
  });
});

// ── A2UISeverity ───────────────────────────────────────────────────────────

describe("A2UISeverity", () => {
  it("accepts all three severity levels", () => {
    const severities: A2UISeverity[] = ["info", "warning", "critical"];
    expect(severities).toHaveLength(3);
  });

  it("critical is a valid severity", () => {
    const s: A2UISeverity = "critical";
    expect(s).toBe("critical");
  });

  it("warning is a valid severity", () => {
    const s: A2UISeverity = "warning";
    expect(s).toBe("warning");
  });
});

// ── A2UIComponent ──────────────────────────────────────────────────────────

describe("A2UIComponent", () => {
  it("constructs a minimal valid component without metadata", () => {
    const component: A2UIComponent = {
      component_id: "comp-001",
      component_type: "card",
      data: { title: "Hello World" },
    };
    expect(component.component_id).toBe("comp-001");
    expect(component.component_type).toBe("card");
    expect(component.data).toEqual({ title: "Hello World" });
    expect(component.metadata).toBeUndefined();
  });

  it("constructs a component with optional metadata", () => {
    const component: A2UIComponent = {
      component_id: "comp-002",
      component_type: "table",
      data: { headers: ["Name", "Value"], rows: [["a", "1"]] },
      metadata: { source: "analytics-agent", version: 2 },
    };
    expect(component.metadata).toHaveProperty("source", "analytics-agent");
    expect(component.metadata).toHaveProperty("version", 2);
  });

  it("component data accepts arbitrary key-value records", () => {
    const component: A2UIComponent = {
      component_id: "comp-003",
      component_type: "chart",
      data: {
        type: "bar",
        labels: ["Jan", "Feb", "Mar"],
        values: [10, 20, 30],
        nested: { deep: true },
      },
    };
    expect(component.data["type"]).toBe("bar");
    expect(component.data["labels"]).toHaveLength(3);
    expect(component.data["nested"]).toEqual({ deep: true });
  });

  it("accepts every valid component_type value", () => {
    const componentTypes: A2UIComponentType[] = [
      "card", "table", "form", "chart", "markdown", "code", "image", "alert", "steps",
    ];
    componentTypes.forEach((ct) => {
      const c: A2UIComponent = {
        component_id: `comp-${ct}`,
        component_type: ct,
        data: {},
      };
      expect(c.component_type).toBe(ct);
    });
  });
});

// ── A2UIRenderMessage ──────────────────────────────────────────────────────

describe("A2UIRenderMessage", () => {
  it("constructs a render message without metadata", () => {
    const msg: A2UIRenderMessage = {
      component_id: "r-001",
      component_type: "markdown",
      data: { content: "# Hello" },
    };
    expect(msg.component_id).toBe("r-001");
    expect(msg.component_type).toBe("markdown");
    expect(msg.data).toHaveProperty("content");
  });

  it("constructs a render message with metadata", () => {
    const msg: A2UIRenderMessage = {
      component_id: "r-002",
      component_type: "code",
      data: { language: "python", code: "print('hi')" },
      metadata: { editable: false },
    };
    expect(msg.metadata).toEqual({ editable: false });
  });

  it("shares the same shape as A2UIComponent", () => {
    const render: A2UIRenderMessage = {
      component_id: "r-003",
      component_type: "alert",
      data: { message: "Warning!" },
    };
    const component: A2UIComponent = render;
    expect(component.component_id).toBe("r-003");
  });
});

// ── A2UIUpdateMessage ──────────────────────────────────────────────────────

describe("A2UIUpdateMessage", () => {
  it("constructs a replace update", () => {
    const msg: A2UIUpdateMessage = {
      component_id: "u-001",
      operation: "replace",
      data: { title: "New Title" },
    };
    expect(msg.operation).toBe("replace");
    expect(msg.data).toHaveProperty("title");
  });

  it("constructs a merge update", () => {
    const msg: A2UIUpdateMessage = {
      component_id: "u-002",
      operation: "merge",
      data: { subtitle: "Added" },
    };
    expect(msg.operation).toBe("merge");
  });

  it("constructs an append update", () => {
    const msg: A2UIUpdateMessage = {
      component_id: "u-003",
      operation: "append",
      data: { rows: [["newrow", "value"]] },
    };
    expect(msg.operation).toBe("append");
  });

  it("accepts all three operation values", () => {
    const operations: Array<A2UIUpdateMessage["operation"]> = [
      "replace",
      "merge",
      "append",
    ];
    expect(operations).toHaveLength(3);
    operations.forEach((op) => {
      const msg: A2UIUpdateMessage = { component_id: "u-x", operation: op, data: {} };
      expect(msg.operation).toBe(op);
    });
  });
});

// ── A2UIRequestInputMessage / A2UIInputRequest ─────────────────────────────

describe("A2UIRequestInputMessage", () => {
  it("constructs a minimal text input request", () => {
    const msg: A2UIRequestInputMessage = {
      request_id: "req-001",
      input_type: "text",
      prompt: "What is your name?",
    };
    expect(msg.request_id).toBe("req-001");
    expect(msg.input_type).toBe("text");
    expect(msg.prompt).toBe("What is your name?");
    expect(msg.options).toBeUndefined();
    expect(msg.validation).toBeUndefined();
  });

  it("constructs a select input request with options", () => {
    const msg: A2UIRequestInputMessage = {
      request_id: "req-002",
      input_type: "select",
      prompt: "Choose a category",
      options: ["Option A", "Option B", "Option C"],
    };
    expect(msg.options).toHaveLength(3);
    expect(msg.options![0]).toBe("Option A");
  });

  it("constructs an input request with validation rules", () => {
    const msg: A2UIRequestInputMessage = {
      request_id: "req-003",
      input_type: "number",
      prompt: "Enter amount (1-1000)",
      validation: { min: 1, max: 1000, integer: true },
    };
    expect(msg.validation).toHaveProperty("min", 1);
    expect(msg.validation).toHaveProperty("max", 1000);
  });

  it("A2UIInputRequest is assignable from A2UIRequestInputMessage", () => {
    const inner: A2UIRequestInputMessage = {
      request_id: "req-004",
      input_type: "date",
      prompt: "Pick a date",
    };
    const alias: A2UIInputRequest = inner;
    expect(alias.request_id).toBe("req-004");
  });
});

// ── A2UIConfirmMessage / A2UIConfirmRequest ────────────────────────────────

describe("A2UIConfirmMessage", () => {
  it("constructs a confirm message without timeout", () => {
    const msg: A2UIConfirmMessage = {
      request_id: "conf-001",
      title: "Are you sure?",
      description: "This action cannot be undone.",
      severity: "warning",
    };
    expect(msg.request_id).toBe("conf-001");
    expect(msg.severity).toBe("warning");
    expect(msg.timeout_seconds).toBeUndefined();
  });

  it("constructs a confirm message with a timeout", () => {
    const msg: A2UIConfirmMessage = {
      request_id: "conf-002",
      title: "Delete account?",
      description: "All data will be permanently removed.",
      severity: "critical",
      timeout_seconds: 30,
    };
    expect(msg.severity).toBe("critical");
    expect(msg.timeout_seconds).toBe(30);
  });

  it("accepts all three severity levels", () => {
    const severities: A2UISeverity[] = ["info", "warning", "critical"];
    severities.forEach((sev) => {
      const msg: A2UIConfirmMessage = {
        request_id: "conf-x",
        title: "Confirm",
        description: "desc",
        severity: sev,
      };
      expect(msg.severity).toBe(sev);
    });
  });

  it("A2UIConfirmRequest is assignable from A2UIConfirmMessage", () => {
    const inner: A2UIConfirmMessage = {
      request_id: "conf-003",
      title: "Proceed?",
      description: "desc",
      severity: "info",
    };
    const alias: A2UIConfirmRequest = inner;
    expect(alias.title).toBe("Proceed?");
  });
});

// ── A2UIProgressMessage / A2UIProgress ────────────────────────────────────

describe("A2UIProgressMessage", () => {
  it("constructs a determinate progress message", () => {
    const msg: A2UIProgressMessage = {
      task_id: "task-001",
      progress_type: "determinate",
      value: 42,
      total: 100,
      message: "Processing…",
    };
    expect(msg.task_id).toBe("task-001");
    expect(msg.progress_type).toBe("determinate");
    expect(msg.value).toBe(42);
    expect(msg.total).toBe(100);
    expect(msg.message).toBe("Processing…");
  });

  it("constructs an indeterminate progress message with no value", () => {
    const msg: A2UIProgressMessage = {
      task_id: "task-002",
      progress_type: "indeterminate",
    };
    expect(msg.value).toBeUndefined();
    expect(msg.total).toBeUndefined();
    expect(msg.message).toBeUndefined();
  });

  it("constructs a streaming progress message", () => {
    const msg: A2UIProgressMessage = {
      task_id: "task-003",
      progress_type: "streaming",
      message: "Streaming tokens…",
    };
    expect(msg.progress_type).toBe("streaming");
    expect(msg.message).toBe("Streaming tokens…");
  });

  it("A2UIProgress is assignable from A2UIProgressMessage", () => {
    const inner: A2UIProgressMessage = {
      task_id: "task-004",
      progress_type: "determinate",
      value: 10,
      total: 50,
    };
    const alias: A2UIProgress = inner;
    expect(alias.task_id).toBe("task-004");
  });
});

// ── A2UINavigateMessage ────────────────────────────────────────────────────

describe("A2UINavigateMessage", () => {
  it("constructs a same-tab navigation message", () => {
    const msg: A2UINavigateMessage = {
      url: "https://agentchains.io/listings",
      new_tab: false,
    };
    expect(msg.url).toBe("https://agentchains.io/listings");
    expect(msg.new_tab).toBe(false);
  });

  it("constructs a new-tab navigation message", () => {
    const msg: A2UINavigateMessage = {
      url: "https://docs.agentchains.io",
      new_tab: true,
    };
    expect(msg.new_tab).toBe(true);
  });
});

// ── A2UINotifyMessage / A2UINotification ───────────────────────────────────

describe("A2UINotifyMessage", () => {
  it("constructs a minimal notification without optional fields", () => {
    const msg: A2UINotifyMessage = {
      level: "info",
      title: "Task complete",
    };
    expect(msg.level).toBe("info");
    expect(msg.title).toBe("Task complete");
    expect(msg.message).toBeUndefined();
    expect(msg.duration_ms).toBeUndefined();
  });

  it("constructs a notification with body and duration", () => {
    const msg: A2UINotifyMessage = {
      level: "error",
      title: "Payment failed",
      message: "Your transaction could not be processed.",
      duration_ms: 6000,
    };
    expect(msg.level).toBe("error");
    expect(msg.message).toBe("Your transaction could not be processed.");
    expect(msg.duration_ms).toBe(6000);
  });

  it("accepts all four notify level values", () => {
    const levels: A2UINotifyLevel[] = ["info", "success", "warning", "error"];
    levels.forEach((level) => {
      const msg: A2UINotifyMessage = { level, title: `${level} notification` };
      expect(msg.level).toBe(level);
    });
  });

  it("A2UINotification is assignable from A2UINotifyMessage", () => {
    const inner: A2UINotifyMessage = {
      level: "success",
      title: "Done!",
    };
    const alias: A2UINotification = inner;
    expect(alias.title).toBe("Done!");
  });
});

// ── A2UISession ────────────────────────────────────────────────────────────

describe("A2UISession", () => {
  it("constructs a connected session", () => {
    const session: A2UISession = {
      session_id: "sess-001",
      agent_id: "agent-abc",
      capabilities: { render: true, input: true },
      status: "connected",
    };
    expect(session.session_id).toBe("sess-001");
    expect(session.agent_id).toBe("agent-abc");
    expect(session.status).toBe("connected");
    expect(session.capabilities).toHaveProperty("render", true);
  });

  it("constructs a connecting session with empty capabilities", () => {
    const session: A2UISession = {
      session_id: "sess-002",
      agent_id: "agent-xyz",
      capabilities: {},
      status: "connecting",
    };
    expect(session.status).toBe("connecting");
    expect(Object.keys(session.capabilities)).toHaveLength(0);
  });

  it("accepts all four status values", () => {
    const statuses: Array<A2UISession["status"]> = [
      "connecting",
      "connected",
      "disconnected",
      "error",
    ];
    statuses.forEach((status) => {
      const session: A2UISession = {
        session_id: "sess-x",
        agent_id: "agent-x",
        capabilities: {},
        status,
      };
      expect(session.status).toBe(status);
    });
  });
});

// ── A2UIState ──────────────────────────────────────────────────────────────

describe("A2UIState", () => {
  it("constructs an initial disconnected state", () => {
    const state: A2UIState = {
      session: null,
      components: new Map(),
      pendingInput: null,
      pendingConfirm: null,
      progress: new Map(),
      notifications: [],
      connected: false,
    };
    expect(state.session).toBeNull();
    expect(state.pendingInput).toBeNull();
    expect(state.pendingConfirm).toBeNull();
    expect(state.connected).toBe(false);
    expect(state.components.size).toBe(0);
    expect(state.progress.size).toBe(0);
    expect(state.notifications).toHaveLength(0);
  });

  it("stores a session when connected", () => {
    const session: A2UISession = {
      session_id: "sess-state-1",
      agent_id: "agent-1",
      capabilities: {},
      status: "connected",
    };
    const state: A2UIState = {
      session,
      components: new Map(),
      pendingInput: null,
      pendingConfirm: null,
      progress: new Map(),
      notifications: [],
      connected: true,
    };
    expect(state.session).not.toBeNull();
    expect(state.session!.status).toBe("connected");
    expect(state.connected).toBe(true);
  });

  it("stores multiple components in the Map", () => {
    const comp1: A2UIComponent = {
      component_id: "c-1",
      component_type: "card",
      data: { title: "Card 1" },
    };
    const comp2: A2UIComponent = {
      component_id: "c-2",
      component_type: "table",
      data: { rows: [] },
    };
    const components = new Map<string, A2UIComponent>([
      ["c-1", comp1],
      ["c-2", comp2],
    ]);
    const state: A2UIState = {
      session: null,
      components,
      pendingInput: null,
      pendingConfirm: null,
      progress: new Map(),
      notifications: [],
      connected: false,
    };
    expect(state.components.size).toBe(2);
    expect(state.components.get("c-1")?.component_type).toBe("card");
    expect(state.components.get("c-2")?.component_type).toBe("table");
  });

  it("stores pending input request", () => {
    const pending: A2UIRequestInputMessage = {
      request_id: "req-state-1",
      input_type: "text",
      prompt: "Enter something",
    };
    const state: A2UIState = {
      session: null,
      components: new Map(),
      pendingInput: pending,
      pendingConfirm: null,
      progress: new Map(),
      notifications: [],
      connected: false,
    };
    expect(state.pendingInput).not.toBeNull();
    expect(state.pendingInput!.request_id).toBe("req-state-1");
    expect(state.pendingInput!.input_type).toBe("text");
  });

  it("stores pending confirmation request", () => {
    const confirm: A2UIConfirmMessage = {
      request_id: "conf-state-1",
      title: "Sure?",
      description: "Yes/no",
      severity: "warning",
      timeout_seconds: 15,
    };
    const state: A2UIState = {
      session: null,
      components: new Map(),
      pendingInput: null,
      pendingConfirm: confirm,
      progress: new Map(),
      notifications: [],
      connected: false,
    };
    expect(state.pendingConfirm).not.toBeNull();
    expect(state.pendingConfirm!.severity).toBe("warning");
    expect(state.pendingConfirm!.timeout_seconds).toBe(15);
  });

  it("tracks progress for multiple concurrent tasks", () => {
    const p1: A2UIProgressMessage = {
      task_id: "t-1",
      progress_type: "determinate",
      value: 75,
      total: 100,
    };
    const p2: A2UIProgressMessage = {
      task_id: "t-2",
      progress_type: "streaming",
    };
    const progress = new Map<string, A2UIProgressMessage>([
      ["t-1", p1],
      ["t-2", p2],
    ]);
    const state: A2UIState = {
      session: null,
      components: new Map(),
      pendingInput: null,
      pendingConfirm: null,
      progress,
      notifications: [],
      connected: false,
    };
    expect(state.progress.size).toBe(2);
    expect(state.progress.get("t-1")?.value).toBe(75);
    expect(state.progress.get("t-2")?.progress_type).toBe("streaming");
  });

  it("stores a list of notifications", () => {
    const n1: A2UINotifyMessage = { level: "info", title: "Note 1" };
    const n2: A2UINotifyMessage = { level: "error", title: "Error!", duration_ms: 5000 };
    const state: A2UIState = {
      session: null,
      components: new Map(),
      pendingInput: null,
      pendingConfirm: null,
      progress: new Map(),
      notifications: [n1, n2],
      connected: false,
    };
    expect(state.notifications).toHaveLength(2);
    expect(state.notifications[0].level).toBe("info");
    expect(state.notifications[1].duration_ms).toBe(5000);
  });
});
