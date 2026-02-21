import { useState, useEffect, useRef, useCallback } from "react";
import {
  Bot,
  Send,
  Wifi,
  WifiOff,
  Cpu,
  Clock,
  MessageSquare,
  ChevronRight,
  Plug,
  Power,
  Loader2,
  History,
  Layers,
  Info,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useA2UI } from "../hooks/useA2UI";
import A2UIContainer from "../components/a2ui/A2UIContainer";
import A2UINotification from "../components/a2ui/A2UINotification";
import A2UIInputDialog from "../components/a2ui/A2UIInputDialog";
import A2UIConfirmDialog from "../components/a2ui/A2UIConfirmDialog";

/**
 * Full A2UI Agent Interaction Page.
 *
 * Renders the A2UIContainer connected via the useA2UI hook, showing:
 * - Session info panel (session ID, status, component count)
 * - Left sidebar with agent info and capabilities list
 * - Center A2UI component renderer with progress overlays
 * - Right sidebar with session history
 * - Chat input bar and input/confirm dialog overlays
 */

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp: Date;
}

export default function AgentInteractionPage() {
  const [agentId, setAgentId] = useState("");
  const [token, setToken] = useState("");
  const [started, setStarted] = useState(false);

  const a2ui = useA2UI(agentId || "__placeholder__", token || "__placeholder__");

  const {
    session,
    components,
    activeInput,
    activeConfirm,
    progress,
    notifications,
    connect,
    disconnect,
    respond,
    approve,
  } = a2ui;

  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const isConnected = session?.status === "connected";

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // Add system message when connection status changes
  useEffect(() => {
    if (session?.status === "connected") {
      addSystemMessage("Connected to agent successfully.");
    } else if (session?.status === "disconnected") {
      addSystemMessage("Disconnected from agent.");
    } else if (session?.status === "error") {
      addSystemMessage("Connection error occurred.");
    }
  }, [session?.status]);

  const addSystemMessage = useCallback((content: string) => {
    setChatHistory((prev) => [
      ...prev,
      {
        id: `sys-${Date.now()}`,
        role: "system",
        content,
        timestamp: new Date(),
      },
    ]);
  }, []);

  const handleConnect = useCallback(async () => {
    if (!agentId.trim() || !token.trim()) return;
    setStarted(true);
    setIsConnecting(true);
    try {
      await connect();
    } catch {
      addSystemMessage("Failed to connect. Please try again.");
    } finally {
      setIsConnecting(false);
    }
  }, [connect, addSystemMessage, agentId, token]);

  const handleDisconnect = useCallback(() => {
    disconnect();
    setStarted(false);
  }, [disconnect]);

  const handleSendMessage = useCallback(() => {
    const trimmed = chatInput.trim();
    if (!trimmed || !isConnected) return;

    setChatHistory((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      },
    ]);

    if (activeInput) {
      respond(activeInput.request_id, trimmed);
    }

    setChatInput("");
    inputRef.current?.focus();
  }, [chatInput, isConnected, activeInput, respond]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    },
    [handleSendMessage],
  );

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const capabilities = session?.capabilities
    ? Object.keys(session.capabilities)
    : [];

  // ── Connection form (not yet started) ──
  if (!started) {
    return (
      <div className="space-y-6 animate-fade-in">
        <PageHeader
          title="Agent Interaction"
          subtitle="Real-time Agent-to-UI communication via A2UI protocol"
          icon={Bot}
        />

        <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-6">
          <div className="mx-auto max-w-md space-y-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[rgba(96,165,250,0.1)]">
                <Bot className="h-5 w-5 text-[#60a5fa]" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#e2e8f0]">Start A2UI Session</h3>
                <p className="text-xs text-[#64748b]">Enter the agent ID and auth token to connect</p>
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[#94a3b8]">Agent ID</label>
              <input
                type="text"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                placeholder="e.g. agent-abc-123"
                className="w-full rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
              />
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-[#94a3b8]">Auth Token</label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Bearer token"
                className="w-full rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-2 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-colors focus:border-[#60a5fa]"
              />
            </div>

            <button
              onClick={handleConnect}
              disabled={!agentId.trim() || !token.trim()}
              className="w-full rounded-lg bg-[#60a5fa] px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#3b82f6] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Connect to Agent
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── Main interaction layout ──
  return (
    <div className="flex h-full flex-col gap-4 animate-fade-in">
      {/* Notifications overlay */}
      <A2UINotification notifications={notifications} />

      {/* Input dialog overlay */}
      {activeInput && (
        <A2UIInputDialog
          request={activeInput}
          onRespond={(requestId, value) => respond(requestId, value)}
        />
      )}

      {/* Confirm dialog overlay */}
      {activeConfirm && (
        <A2UIConfirmDialog
          confirm={activeConfirm}
          onApprove={(requestId, approved, reason) => approve(requestId, approved, reason)}
        />
      )}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#60a5fa] to-[#a78bfa] shadow-[0_0_20px_rgba(96,165,250,0.2)]">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-[#e2e8f0]">
              Agent Interaction
            </h1>
            <p className="text-xs font-mono text-[#64748b]">
              {agentId.slice(0, 12)}...
            </p>
          </div>
        </div>

        <button
          onClick={isConnected ? handleDisconnect : handleConnect}
          disabled={isConnecting}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
            isConnected
              ? "border border-[rgba(248,113,113,0.2)] bg-[rgba(248,113,113,0.06)] text-[#f87171] hover:bg-[rgba(248,113,113,0.12)]"
              : "border border-[rgba(52,211,153,0.2)] bg-[rgba(52,211,153,0.06)] text-[#34d399] hover:bg-[rgba(52,211,153,0.12)]"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {isConnecting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : isConnected ? (
            <Power className="h-4 w-4" />
          ) : (
            <Plug className="h-4 w-4" />
          )}
          {isConnecting
            ? "Connecting..."
            : isConnected
              ? "Disconnect"
              : "Connect"}
        </button>
      </div>

      {/* Session info bar */}
      {session && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
            <div className="flex items-center gap-2 mb-1">
              <Info className="h-3.5 w-3.5 text-[#60a5fa]" />
              <p className="text-[10px] font-medium uppercase tracking-wider text-[#64748b]">Session</p>
            </div>
            <p className="text-xs font-mono text-[#e2e8f0] truncate">
              {session.session_id?.slice(0, 16) ?? "N/A"}
            </p>
          </div>

          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
            <div className="flex items-center gap-2 mb-1">
              <Layers className="h-3.5 w-3.5 text-[#a78bfa]" />
              <p className="text-[10px] font-medium uppercase tracking-wider text-[#64748b]">Components</p>
            </div>
            <p className="text-lg font-bold text-[#e2e8f0]">{components.length}</p>
          </div>

          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
            <div className="flex items-center gap-2 mb-1">
              <Loader2 className="h-3.5 w-3.5 text-[#fbbf24]" />
              <p className="text-[10px] font-medium uppercase tracking-wider text-[#64748b]">Active Tasks</p>
            </div>
            <p className="text-lg font-bold text-[#e2e8f0]">{progress.size}</p>
          </div>

          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
            <div className="flex items-center gap-2 mb-1">
              {isConnected ? (
                <Wifi className="h-3.5 w-3.5 text-[#34d399]" />
              ) : (
                <WifiOff className="h-3.5 w-3.5 text-[#64748b]" />
              )}
              <p className="text-[10px] font-medium uppercase tracking-wider text-[#64748b]">Status</p>
            </div>
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase"
              style={{
                backgroundColor: isConnected ? "rgba(52,211,153,0.15)" : "rgba(100,116,139,0.15)",
                color: isConnected ? "#34d399" : "#64748b",
              }}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: isConnected ? "#34d399" : "#64748b" }}
              />
              {session.status}
            </span>
          </div>
        </div>
      )}

      {/* Three-panel layout */}
      <div className="grid flex-1 grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[280px_1fr_280px]">
        {/* Left Panel: Agent Info + Capabilities */}
        <div className="hidden flex-col gap-4 overflow-y-auto lg:flex">
          <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-[#60a5fa] to-[#a78bfa] text-lg font-bold text-white">
                {agentId.charAt(0).toUpperCase()}
              </div>
              <div>
                <p className="text-sm font-semibold text-[#e2e8f0]">
                  Agent {agentId.slice(0, 8)}
                </p>
                <div className="mt-0.5 flex items-center gap-1.5">
                  {isConnected ? (
                    <>
                      <Wifi className="h-3 w-3 text-[#34d399]" />
                      <span className="text-[10px] text-[#34d399]">Online</span>
                    </>
                  ) : (
                    <>
                      <WifiOff className="h-3 w-3 text-[#64748b]" />
                      <span className="text-[10px] text-[#64748b]">Offline</span>
                    </>
                  )}
                </div>
              </div>
            </div>

            {session && (
              <div className="space-y-2 border-t border-[rgba(255,255,255,0.06)] pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase tracking-wider text-[#64748b]">Session</span>
                  <span className="text-[10px] font-mono text-[#94a3b8]">
                    {session.session_id?.slice(0, 12)}...
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Capabilities */}
          <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-5">
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="h-3.5 w-3.5 text-[#a78bfa]" />
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#94a3b8]">
                Capabilities
              </p>
            </div>
            {capabilities.length === 0 ? (
              <p className="text-xs text-[#475569] italic">
                {isConnected ? "No capabilities reported" : "Connect to view capabilities"}
              </p>
            ) : (
              <div className="flex flex-col gap-1.5">
                {capabilities.map((cap) => (
                  <div
                    key={cap}
                    className="flex items-center gap-2 rounded-lg border border-[rgba(96,165,250,0.1)] bg-[rgba(96,165,250,0.04)] px-3 py-2"
                  >
                    <ChevronRight className="h-3 w-3 text-[#60a5fa]" />
                    <span className="text-xs text-[#e2e8f0]">{cap}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Center Panel: A2UI Container */}
        <div className="flex flex-col overflow-hidden rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#0d1220]">
          <div className="flex items-center gap-2 border-b border-[rgba(255,255,255,0.06)] bg-[#141928] px-5 py-3">
            <MessageSquare className="h-3.5 w-3.5 text-[#60a5fa]" />
            <span className="text-xs font-semibold text-[#94a3b8] uppercase tracking-wider">
              Agent UI
            </span>
            {progress.size > 0 && (
              <span className="ml-auto inline-flex items-center gap-1 text-[10px] text-[#60a5fa]">
                <Loader2 className="h-3 w-3 animate-spin" />
                {progress.size} task{progress.size !== 1 ? "s" : ""} running
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-5">
            {!isConnected ? (
              <div className="flex flex-col items-center justify-center h-full gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)]">
                  <Bot className="h-8 w-8 text-[#60a5fa]" />
                </div>
                <p className="text-sm font-medium text-[#94a3b8]">
                  Connect to start interacting
                </p>
                <p className="text-xs text-[#64748b] text-center max-w-xs">
                  Click the Connect button above to establish a real-time session
                  with this agent.
                </p>
              </div>
            ) : (
              <A2UIContainer
                components={components}
                progress={progress}
                onFormSubmit={(componentId, values) => {
                  respond(componentId, values);
                }}
              />
            )}
          </div>

          {/* Chat input bar */}
          <div className="border-t border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
            <div className="flex items-center gap-3">
              <input
                ref={inputRef}
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  isConnected
                    ? activeInput
                      ? activeInput.prompt
                      : "Type a message..."
                    : "Connect to send messages"
                }
                disabled={!isConnected}
                className="flex-1 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#0d1220] px-4 py-3 text-sm text-[#e2e8f0] placeholder-[#475569] outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
              />
              <button
                onClick={handleSendMessage}
                disabled={!isConnected || !chatInput.trim()}
                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-[#60a5fa] text-[#0a0e1a] transition-all duration-200 hover:bg-[#3b82f6] active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
                title="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel: Session History */}
        <div className="hidden flex-col gap-4 overflow-y-auto lg:flex">
          <div className="flex flex-1 flex-col rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden">
            <div className="flex items-center gap-2 border-b border-[rgba(255,255,255,0.06)] px-5 py-3">
              <History className="h-3.5 w-3.5 text-[#fbbf24]" />
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#94a3b8]">
                Session History
              </p>
              <span className="ml-auto text-[10px] text-[#475569]">
                {chatHistory.length} message{chatHistory.length !== 1 ? "s" : ""}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {chatHistory.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full gap-2 py-8">
                  <Clock className="h-6 w-6 text-[#475569]" />
                  <p className="text-xs text-[#475569]">No messages yet</p>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {chatHistory.map((msg) => (
                    <div
                      key={msg.id}
                      className="rounded-lg p-2.5"
                      style={{
                        backgroundColor:
                          msg.role === "user"
                            ? "rgba(96,165,250,0.06)"
                            : msg.role === "agent"
                              ? "rgba(52,211,153,0.06)"
                              : "rgba(255,255,255,0.02)",
                        borderLeft: `2px solid ${
                          msg.role === "user"
                            ? "#60a5fa"
                            : msg.role === "agent"
                              ? "#34d399"
                              : "#475569"
                        }`,
                      }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className="text-[9px] font-semibold uppercase"
                          style={{
                            color:
                              msg.role === "user"
                                ? "#60a5fa"
                                : msg.role === "agent"
                                  ? "#34d399"
                                  : "#475569",
                          }}
                        >
                          {msg.role}
                        </span>
                        <span className="text-[9px] text-[#475569]">
                          {formatTime(msg.timestamp)}
                        </span>
                      </div>
                      <p className="text-xs text-[#94a3b8] leading-relaxed">
                        {msg.content}
                      </p>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
