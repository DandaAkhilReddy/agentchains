// ── A2UI (Agent-to-User Interface) Type Definitions ──
// Matches backend A2UI JSON-RPC schemas

/** Supported component types for the A2UI rendering layer */
export type A2UIComponentType =
  | "card"
  | "table"
  | "form"
  | "chart"
  | "markdown"
  | "code"
  | "image"
  | "alert"
  | "steps";

/** Progress bar display modes */
export type A2UIProgressType = "determinate" | "indeterminate" | "streaming";

/** Supported user input field types */
export type A2UIInputType = "text" | "select" | "number" | "date" | "file";

/** Notification severity levels */
export type A2UINotifyLevel = "info" | "success" | "warning" | "error";

/** Confirmation dialog severity */
export type A2UISeverity = "info" | "warning" | "critical";

/** A rendered UI component from an agent */
export interface A2UIComponent {
  component_id: string;
  component_type: A2UIComponentType;
  data: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

/** Message to render a new component in the UI */
export interface A2UIRenderMessage {
  component_id: string;
  component_type: A2UIComponentType;
  data: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

/** Message to update an existing component */
export interface A2UIUpdateMessage {
  component_id: string;
  operation: "replace" | "merge" | "append";
  data: Record<string, unknown>;
}

/** Agent requests user input (internal wire format) */
export interface A2UIRequestInputMessage {
  request_id: string;
  input_type: A2UIInputType;
  prompt: string;
  options?: string[];
  validation?: Record<string, unknown>;
}

/** Agent requests user input (public alias) */
export type A2UIInputRequest = A2UIRequestInputMessage;

/** Agent requests user confirmation (internal wire format) */
export interface A2UIConfirmMessage {
  request_id: string;
  title: string;
  description: string;
  severity: A2UISeverity;
  timeout_seconds?: number;
}

/** Agent requests user confirmation (public alias) */
export type A2UIConfirmRequest = A2UIConfirmMessage;

/** Progress update from agent task (internal wire format) */
export interface A2UIProgressMessage {
  task_id: string;
  progress_type: A2UIProgressType;
  value?: number;
  total?: number;
  message?: string;
}

/** Progress update from agent task (public alias) */
export type A2UIProgress = A2UIProgressMessage;

/** Navigate to a URL */
export interface A2UINavigateMessage {
  url: string;
  new_tab: boolean;
}

/** Toast notification from agent (internal wire format) */
export interface A2UINotifyMessage {
  level: A2UINotifyLevel;
  title: string;
  message?: string;
  duration_ms?: number;
}

/** Toast notification from agent (public alias) */
export type A2UINotification = A2UINotifyMessage;

/** Active A2UI session state */
export interface A2UISession {
  session_id: string;
  agent_id: string;
  capabilities: Record<string, unknown>;
  status: "connecting" | "connected" | "disconnected" | "error";
}

/** Top-level state for the A2UI hook */
export interface A2UIState {
  session: A2UISession | null;
  components: Map<string, A2UIComponent>;
  pendingInput: A2UIRequestInputMessage | null;
  pendingConfirm: A2UIConfirmMessage | null;
  progress: Map<string, A2UIProgressMessage>;
  notifications: A2UINotifyMessage[];
  connected: boolean;
}
