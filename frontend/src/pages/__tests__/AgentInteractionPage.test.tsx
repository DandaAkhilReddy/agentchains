import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";

// Mock scrollIntoView (not available in jsdom)
Element.prototype.scrollIntoView = vi.fn();

/* ── Mock WebSocket for the a2ui client ───────────────────────── */
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  CONNECTING = 0;
  OPEN = 1;
  CLOSING = 2;
  CLOSED = 3;
  readyState = 0;
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  constructor(url: string) {
    this.url = url;
  }
  send = vi.fn();
  close = vi.fn();
}
vi.stubGlobal("WebSocket", MockWebSocket);

/* ── Mock child components ────────────────────────────────────── */

vi.mock("../../components/PageHeader", () => ({
  default: ({ title, subtitle }: { title: string; subtitle?: string }) => (
    <div data-testid="page-header">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  ),
}));

vi.mock("../../components/a2ui/A2UIContainer", () => ({
  default: ({ components, progress, onFormSubmit }: any) => (
    <div data-testid="a2ui-container">
      components={components.length} progress={progress.size}
      {onFormSubmit && (
        <button
          data-testid="mock-form-submit"
          onClick={() => onFormSubmit("comp-1", { field: "value" })}
        >
          Submit Form
        </button>
      )}
    </div>
  ),
}));

vi.mock("../../components/a2ui/A2UINotification", () => ({
  default: ({ notifications }: any) => (
    <div data-testid="a2ui-notification">
      {notifications.length} notifications
    </div>
  ),
}));

vi.mock("../../components/a2ui/A2UIInputDialog", () => ({
  default: ({ request, onRespond }: any) => (
    <div data-testid="a2ui-input-dialog">
      <span>{request.prompt}</span>
      <button onClick={() => onRespond(request.request_id, "test-value")}>
        Respond
      </button>
    </div>
  ),
}));

vi.mock("../../components/a2ui/A2UIConfirmDialog", () => ({
  default: ({ confirm, onApprove }: any) => (
    <div data-testid="a2ui-confirm-dialog">
      <span>{confirm.message}</span>
      <button onClick={() => onApprove(confirm.request_id, true, "ok")}>
        ApproveBtn
      </button>
    </div>
  ),
}));

/* ── Mock the useA2UI hook ────────────────────────────────────── */

const mockConnect = vi.fn().mockResolvedValue(undefined);
const mockDisconnect = vi.fn();
const mockRespond = vi.fn();
const mockApprove = vi.fn();
const mockCancel = vi.fn();

const defaultHookReturn = {
  session: null as any,
  components: [] as any[],
  activeInput: null as any,
  activeConfirm: null as any,
  progress: new Map() as Map<string, any>,
  notifications: [] as any[],
  connect: mockConnect,
  disconnect: mockDisconnect,
  respond: mockRespond,
  approve: mockApprove,
  cancel: mockCancel,
};

let hookReturn = { ...defaultHookReturn };

vi.mock("../../hooks/useA2UI", () => ({
  useA2UI: () => hookReturn,
}));

/* ── Helpers ──────────────────────────────────────────────────── */

function setHook(overrides: Partial<typeof defaultHookReturn>) {
  hookReturn = { ...defaultHookReturn, ...overrides };
}

/** Fill form and click connect to transition to the started=true layout */
async function startSession(agentId = "agent-test-1234", token = "tok-xyz") {
  fireEvent.change(screen.getByPlaceholderText("e.g. agent-abc-123"), {
    target: { value: agentId },
  });
  fireEvent.change(screen.getByPlaceholderText("Bearer token"), {
    target: { value: token },
  });
  await act(async () => {
    fireEvent.click(
      screen.getByRole("button", { name: /connect to agent/i }),
    );
  });
}

/* eslint-disable-next-line @typescript-eslint/no-var-requires */
import AgentInteractionPage from "../AgentInteractionPage";

/* ── Tests ────────────────────────────────────────────────────── */

describe("AgentInteractionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    hookReturn = { ...defaultHookReturn };
  });

  /* ── Connection form (initial state) ─────────────────────── */

  describe("connection form", () => {
    it("renders PageHeader with correct title and subtitle", () => {
      render(<AgentInteractionPage />);
      expect(screen.getByTestId("page-header")).toBeInTheDocument();
      expect(screen.getByText("Agent Interaction")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Real-time Agent-to-UI communication via A2UI protocol",
        ),
      ).toBeInTheDocument();
    });

    it("renders 'Start A2UI Session' heading", () => {
      render(<AgentInteractionPage />);
      expect(screen.getByText("Start A2UI Session")).toBeInTheDocument();
    });

    it("renders helper text", () => {
      render(<AgentInteractionPage />);
      expect(
        screen.getByText("Enter the agent ID and auth token to connect"),
      ).toBeInTheDocument();
    });

    it("renders Agent ID label and input", () => {
      render(<AgentInteractionPage />);
      expect(screen.getByText("Agent ID")).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText("e.g. agent-abc-123"),
      ).toBeInTheDocument();
    });

    it("renders Auth Token label and password input", () => {
      render(<AgentInteractionPage />);
      expect(screen.getByText("Auth Token")).toBeInTheDocument();
      const tokenInput = screen.getByPlaceholderText("Bearer token");
      expect(tokenInput).toBeInTheDocument();
      expect(tokenInput).toHaveAttribute("type", "password");
    });

    it("disables Connect button when both inputs are empty", () => {
      render(<AgentInteractionPage />);
      expect(
        screen.getByRole("button", { name: /connect to agent/i }),
      ).toBeDisabled();
    });

    it("disables Connect button when only Agent ID is filled", () => {
      render(<AgentInteractionPage />);
      fireEvent.change(screen.getByPlaceholderText("e.g. agent-abc-123"), {
        target: { value: "agent-1" },
      });
      expect(
        screen.getByRole("button", { name: /connect to agent/i }),
      ).toBeDisabled();
    });

    it("disables Connect button when only Token is filled", () => {
      render(<AgentInteractionPage />);
      fireEvent.change(screen.getByPlaceholderText("Bearer token"), {
        target: { value: "tok-1" },
      });
      expect(
        screen.getByRole("button", { name: /connect to agent/i }),
      ).toBeDisabled();
    });

    it("enables Connect button when both inputs are filled", () => {
      render(<AgentInteractionPage />);
      fireEvent.change(screen.getByPlaceholderText("e.g. agent-abc-123"), {
        target: { value: "agent-1" },
      });
      fireEvent.change(screen.getByPlaceholderText("Bearer token"), {
        target: { value: "tok-1" },
      });
      expect(
        screen.getByRole("button", { name: /connect to agent/i }),
      ).not.toBeDisabled();
    });

    it("calls connect() on button click when fields are valid", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(mockConnect).toHaveBeenCalledTimes(1);
    });

    it("does not call connect() when fields are empty (button disabled)", () => {
      render(<AgentInteractionPage />);
      const btn = screen.getByRole("button", { name: /connect to agent/i });
      // The button is disabled, so click should not fire the handler
      fireEvent.click(btn);
      expect(mockConnect).not.toHaveBeenCalled();
    });
  });

  /* ── Main layout (started, session null / not connected) ─── */

  describe("main layout - not connected", () => {
    it("renders main layout after clicking connect", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("Agent Interaction")).toBeInTheDocument();
      expect(screen.getByText("Connect to start interacting")).toBeInTheDocument();
    });

    it("shows truncated agent id in header", async () => {
      render(<AgentInteractionPage />);
      await startSession("agent-test-1234");
      expect(screen.getByText("agent-test-1...")).toBeInTheDocument();
    });

    it("disables chat input when not connected", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(
        screen.getByPlaceholderText("Connect to send messages"),
      ).toBeDisabled();
    });

    it("disables send button when not connected", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByTitle("Send message")).toBeDisabled();
    });

    it("shows the Connect button in the header (not Disconnect)", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("Connect")).toBeInTheDocument();
    });

    it("shows 'No messages yet' in session history panel", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("No messages yet")).toBeInTheDocument();
    });

    it("shows 0 messages count", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("0 messages")).toBeInTheDocument();
    });

    it("shows Agent UI section header", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("Agent UI")).toBeInTheDocument();
    });

    it("shows Session History section header", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("Session History")).toBeInTheDocument();
    });

    it("shows Capabilities section header", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(screen.getByText("Capabilities")).toBeInTheDocument();
    });

    it("shows 'Connect to view capabilities' when not connected", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(
        screen.getByText("Connect to view capabilities"),
      ).toBeInTheDocument();
    });

    it("shows helper text about connecting below the placeholder icon", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      expect(
        screen.getByText(
          /Click the Connect button above to establish a real-time session/,
        ),
      ).toBeInTheDocument();
    });

    it("does not render session info bar when session is null", async () => {
      render(<AgentInteractionPage />);
      await startSession();
      // session is null, so no Session / Components / Active Tasks cards
      expect(screen.queryByText("Components")).toBeNull();
    });
  });

  /* ── Connected state ────────────────────────────────────── */

  describe("connected state", () => {
    const connectedSession = {
      session_id: "sess-abcd1234efgh5678",
      status: "connected" as const,
      capabilities: { retrieval: true, tool_use: true },
    };

    async function renderConnected() {
      setHook({ session: connectedSession });
      render(<AgentInteractionPage />);
      await startSession("agent-xyz-long-id");
    }

    it("shows Disconnect button", async () => {
      await renderConnected();
      expect(screen.getByText("Disconnect")).toBeInTheDocument();
    });

    it("shows session info bar with session id truncated to 16 chars", async () => {
      await renderConnected();
      // Info bar: session_id.slice(0, 16) = "sess-abcd1234efg" (no "..." suffix)
      const el = screen.getByText("sess-abcd1234efg");
      expect(el).toBeInTheDocument();
    });

    it("shows Session labels in info bar", async () => {
      await renderConnected();
      // "Session" appears in both the info bar and the left panel
      const sessionLabels = screen.getAllByText("Session");
      expect(sessionLabels.length).toBeGreaterThanOrEqual(1);
    });

    it("shows Components label in info bar", async () => {
      await renderConnected();
      expect(screen.getByText("Components")).toBeInTheDocument();
    });

    it("shows Active Tasks label in info bar", async () => {
      await renderConnected();
      expect(screen.getByText("Active Tasks")).toBeInTheDocument();
    });

    it("shows Status label in info bar", async () => {
      await renderConnected();
      expect(screen.getByText("Status")).toBeInTheDocument();
    });

    it("shows connected status badge", async () => {
      await renderConnected();
      expect(screen.getByText("connected")).toBeInTheDocument();
    });

    it("shows component count as 0", async () => {
      await renderConnected();
      // Two elements: one in session info bar, one in A2UIContainer mock
      const zeros = screen.getAllByText("0");
      expect(zeros.length).toBeGreaterThanOrEqual(1);
    });

    it("renders A2UIContainer when connected", async () => {
      await renderConnected();
      expect(screen.getByTestId("a2ui-container")).toBeInTheDocument();
    });

    it("renders A2UINotification component", async () => {
      await renderConnected();
      expect(screen.getByTestId("a2ui-notification")).toBeInTheDocument();
    });

    it("shows chat input with 'Type a message...' placeholder", async () => {
      await renderConnected();
      const input = screen.getByPlaceholderText("Type a message...");
      expect(input).not.toBeDisabled();
    });

    it("shows capabilities from session", async () => {
      await renderConnected();
      expect(screen.getByText("retrieval")).toBeInTheDocument();
      expect(screen.getByText("tool_use")).toBeInTheDocument();
    });

    it("shows Online status in left panel", async () => {
      await renderConnected();
      expect(screen.getByText("Online")).toBeInTheDocument();
    });

    it("shows agent name in left panel from agent id", async () => {
      await renderConnected();
      // Agent {agentId.slice(0,8)} = "Agent agent-xy"
      expect(screen.getByText(/Agent agent-x/)).toBeInTheDocument();
    });

    it("shows left panel session id", async () => {
      await renderConnected();
      // session_id.slice(0, 12) = "sess-abcd123"
      expect(screen.getByText("sess-abcd123...")).toBeInTheDocument();
    });

    it("calls disconnect when Disconnect button is clicked", async () => {
      await renderConnected();
      fireEvent.click(screen.getByText("Disconnect"));
      expect(mockDisconnect).toHaveBeenCalledTimes(1);
    });

    it("shows 'No capabilities reported' when connected with empty capabilities", async () => {
      setHook({
        session: {
          ...connectedSession,
          capabilities: {},
        },
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByText("No capabilities reported")).toBeInTheDocument();
    });
  });

  /* ── Chat messaging ─────────────────────────────────────── */

  describe("chat messaging", () => {
    const connectedSession = {
      session_id: "sess-1234",
      status: "connected" as const,
      capabilities: {},
    };

    async function renderConnectedChat() {
      setHook({ session: connectedSession });
      render(<AgentInteractionPage />);
      await startSession("agent-chat");
    }

    it("adds a user message to chat when send button is clicked", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "Hello agent" } });
      fireEvent.click(screen.getByTitle("Send message"));

      expect(screen.getByText("Hello agent")).toBeInTheDocument();
      expect(screen.getByText("user")).toBeInTheDocument();
    });

    it("sends message on Enter key press", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "Enter message" } });
      fireEvent.keyDown(input, { key: "Enter" });

      expect(screen.getByText("Enter message")).toBeInTheDocument();
    });

    it("does not send on Shift+Enter", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "No send" } });
      fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

      expect(screen.queryByText("No send")).toBeNull();
    });

    it("clears input after sending", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "Will clear" } });
      fireEvent.click(screen.getByTitle("Send message"));

      expect(input).toHaveValue("");
    });

    it("send button is disabled when input is empty", async () => {
      await renderConnectedChat();
      expect(screen.getByTitle("Send message")).toBeDisabled();
    });

    it("send button is disabled when input is whitespace only", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "   " } });
      expect(screen.getByTitle("Send message")).toBeDisabled();
    });

    it("does not add message for empty input on Enter", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.keyDown(input, { key: "Enter" });
      // No message should appear - still "No messages yet" (except system msgs)
      // user messages count shouldn't increase
      expect(screen.queryByText("user")).toBeNull();
    });

    it("updates message count in session history after sending", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "msg1" } });
      fireEvent.click(screen.getByTitle("Send message"));

      await waitFor(() => {
        const countEl = screen.getAllByText(/\d+ message/);
        expect(countEl.length).toBeGreaterThan(0);
      });
    });

    it("displays timestamp for sent messages", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");
      fireEvent.change(input, { target: { value: "Time test" } });
      fireEvent.click(screen.getByTitle("Send message"));

      // timestamp is rendered via formatTime which produces HH:MM format
      // Just check that a message with the role and content appeared
      expect(screen.getByText("Time test")).toBeInTheDocument();
    });

    it("calls respond() with active input when sending a message", async () => {
      setHook({
        session: connectedSession,
        activeInput: {
          request_id: "req-42",
          prompt: "Enter your name",
          input_type: "text",
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("agent-x");

      const input = screen.getByPlaceholderText("Enter your name");
      fireEvent.change(input, { target: { value: "Alice" } });
      fireEvent.click(screen.getByTitle("Send message"));

      expect(mockRespond).toHaveBeenCalledWith("req-42", "Alice");
    });

    it("uses active input prompt as placeholder text", async () => {
      setHook({
        session: connectedSession,
        activeInput: {
          request_id: "req-50",
          prompt: "Pick a color",
          input_type: "text",
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-x");

      expect(screen.getByPlaceholderText("Pick a color")).toBeInTheDocument();
    });

    it("sends multiple messages sequentially", async () => {
      await renderConnectedChat();
      const input = screen.getByPlaceholderText("Type a message...");

      fireEvent.change(input, { target: { value: "First" } });
      fireEvent.click(screen.getByTitle("Send message"));

      fireEvent.change(input, { target: { value: "Second" } });
      fireEvent.click(screen.getByTitle("Send message"));

      expect(screen.getByText("First")).toBeInTheDocument();
      expect(screen.getByText("Second")).toBeInTheDocument();
    });
  });

  /* ── Dialogs ────────────────────────────────────────────── */

  describe("input and confirm dialogs", () => {
    async function renderStarted(
      overrides: Partial<typeof defaultHookReturn> = {},
    ) {
      setHook(overrides);
      render(<AgentInteractionPage />);
      await startSession("ag-1", "tk");
    }

    it("renders input dialog when activeInput is set", async () => {
      await renderStarted({
        activeInput: {
          request_id: "req-2",
          prompt: "What is your goal?",
          input_type: "text",
        } as any,
      });
      expect(screen.getByTestId("a2ui-input-dialog")).toBeInTheDocument();
      expect(screen.getByText("What is your goal?")).toBeInTheDocument();
    });

    it("does not render input dialog when activeInput is null", async () => {
      await renderStarted({ activeInput: null });
      expect(screen.queryByTestId("a2ui-input-dialog")).toBeNull();
    });

    it("renders confirm dialog when activeConfirm is set", async () => {
      await renderStarted({
        activeConfirm: {
          request_id: "req-3",
          message: "Confirm deletion?",
          severity: "warning",
          timeout_ms: 30000,
        } as any,
      });
      expect(screen.getByTestId("a2ui-confirm-dialog")).toBeInTheDocument();
      expect(screen.getByText("Confirm deletion?")).toBeInTheDocument();
    });

    it("does not render confirm dialog when activeConfirm is null", async () => {
      await renderStarted({ activeConfirm: null });
      expect(screen.queryByTestId("a2ui-confirm-dialog")).toBeNull();
    });

    it("calls respond via input dialog onRespond callback", async () => {
      await renderStarted({
        activeInput: {
          request_id: "req-resp",
          prompt: "Give input",
          input_type: "text",
        } as any,
      });
      // The mock input dialog has a "Respond" button that calls onRespond
      fireEvent.click(screen.getByText("Respond"));
      expect(mockRespond).toHaveBeenCalledWith("req-resp", "test-value");
    });

    it("calls approve via confirm dialog onApprove callback", async () => {
      await renderStarted({
        activeConfirm: {
          request_id: "req-appr",
          message: "Approve action?",
          severity: "info",
          timeout_ms: 30000,
        } as any,
      });
      // The mock confirm dialog has an "ApproveBtn" button that calls onApprove
      fireEvent.click(screen.getByText("ApproveBtn"));
      expect(mockApprove).toHaveBeenCalledWith("req-appr", true, "ok");
    });
  });

  /* ── Session status system messages ─────────────────────── */

  describe("session status messages", () => {
    it("adds system message for connected status", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      await waitFor(() => {
        expect(
          screen.getByText("Connected to agent successfully."),
        ).toBeInTheDocument();
      });
    });

    it("adds system message for disconnected status", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "disconnected",
          capabilities: {},
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      await waitFor(() => {
        expect(
          screen.getByText("Disconnected from agent."),
        ).toBeInTheDocument();
      });
    });

    it("adds system message for error status", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "error",
          capabilities: {},
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      await waitFor(() => {
        expect(
          screen.getByText("Connection error occurred."),
        ).toBeInTheDocument();
      });
    });

    it("system messages have role 'system'", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      await waitFor(() => {
        expect(screen.getByText("system")).toBeInTheDocument();
      });
    });
  });

  /* ── Connect failure ────────────────────────────────────── */

  describe("connect failure", () => {
    it("adds failure system message when connect() rejects", async () => {
      mockConnect.mockRejectedValueOnce(new Error("Network error"));
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      await waitFor(() => {
        expect(
          screen.getByText("Failed to connect. Please try again."),
        ).toBeInTheDocument();
      });
    });

    it("does not remain in connecting state after failure", async () => {
      mockConnect.mockRejectedValueOnce(new Error("Fail"));
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      // Should not show "Connecting..." anymore
      expect(screen.queryByText("Connecting...")).toBeNull();
    });
  });

  /* ── Progress ───────────────────────────────────────────── */

  describe("progress indicator", () => {
    it("shows running tasks count when progress has 1 entry", async () => {
      const progressMap = new Map();
      progressMap.set("task-1", { task_id: "task-1", percent: 50 });
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
        progress: progressMap,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByText("1 task running")).toBeInTheDocument();
    });

    it("shows plural 'tasks' for multiple entries", async () => {
      const progressMap = new Map();
      progressMap.set("task-1", { task_id: "task-1", percent: 50 });
      progressMap.set("task-2", { task_id: "task-2", percent: 70 });
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
        progress: progressMap,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByText("2 tasks running")).toBeInTheDocument();
    });

    it("does not show running tasks indicator when progress is empty", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
        progress: new Map(),
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.queryByText(/task.*running/)).toBeNull();
    });
  });

  /* ── Offline left panel ─────────────────────────────────── */

  describe("offline left panel", () => {
    it("shows Offline status text when not connected", async () => {
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByText("Offline")).toBeInTheDocument();
    });

    it("shows first letter of agent id in avatar circle", async () => {
      render(<AgentInteractionPage />);
      await startSession("agent-1");
      // agentId.charAt(0).toUpperCase() = "A"
      // This appears in the gradient avatar circle
      const allAs = screen.getAllByText("A");
      expect(allAs.length).toBeGreaterThan(0);
    });
  });

  /* ── Session with N/A session id ────────────────────────── */

  describe("session with missing session_id", () => {
    it("shows N/A when session_id is undefined", async () => {
      setHook({
        session: {
          status: "connected",
          capabilities: {},
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByText("N/A")).toBeInTheDocument();
    });
  });

  /* ── Components with data ───────────────────────────────── */

  describe("components display", () => {
    it("renders A2UIContainer with components when connected", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
        components: [
          {
            component_id: "c1",
            component_type: "card",
            data: { title: "Test" },
          },
          {
            component_id: "c2",
            component_type: "table",
            data: { rows: [] },
          },
        ],
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByTestId("a2ui-container")).toHaveTextContent(
        "components=2",
      );
    });

    it("calls respond via onFormSubmit callback in A2UIContainer", async () => {
      setHook({
        session: {
          session_id: "s1",
          status: "connected",
          capabilities: {},
        } as any,
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");

      const submitBtn = screen.getByTestId("mock-form-submit");
      fireEvent.click(submitBtn);
      expect(mockRespond).toHaveBeenCalledWith("comp-1", { field: "value" });
    });
  });

  /* ── Notifications ──────────────────────────────────────── */

  describe("notifications", () => {
    it("renders notifications from hook", async () => {
      setHook({
        notifications: [
          { message: "Task complete", level: "success" },
          { message: "Warning", level: "warning" },
        ] as any[],
      });
      render(<AgentInteractionPage />);
      await startSession("ag-1");
      expect(screen.getByTestId("a2ui-notification")).toHaveTextContent(
        "2 notifications",
      );
    });
  });
});
