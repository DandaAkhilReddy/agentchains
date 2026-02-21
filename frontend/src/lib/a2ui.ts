import type {
  A2UISession,
  A2UIRenderMessage,
  A2UIUpdateMessage,
  A2UIRequestInputMessage,
  A2UIConfirmMessage,
  A2UIProgressMessage,
  A2UINavigateMessage,
  A2UINotifyMessage,
} from "../types/a2ui";

/** JSON-RPC 2.0 message envelope */
interface JsonRpcRequest {
  jsonrpc: "2.0";
  method: string;
  params?: Record<string, any>;
  id?: string;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  result?: any;
  error?: { code: number; message: string; data?: any };
  id?: string;
}

type MessageHandler = (params: any) => void;

/**
 * A2UI WebSocket client implementing the A2UI JSON-RPC protocol.
 *
 * Handles connection lifecycle, heartbeat, reconnection with
 * exponential backoff, and dispatching server-pushed methods
 * to registered handlers.
 */
export class A2UIClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnects = 5;
  private heartbeatInterval: ReturnType<typeof setInterval> | null = null;
  private handlers: Map<string, MessageHandler> = new Map();
  private pendingRequests: Map<
    string,
    { resolve: (v: any) => void; reject: (e: Error) => void }
  > = new Map();
  private nextId = 0;

  constructor(
    private baseUrl: string,
    private token: string,
  ) {
    // Derive WebSocket URL from the base URL
    const protocol = baseUrl.startsWith("https") ? "wss:" : "ws:";
    const host = baseUrl.replace(/^https?:\/\//, "");
    this.wsUrl = `${protocol}//${host}/ws/v4/a2ui`;
  }

  private wsUrl: string;

  /** Establish the WebSocket connection and wire up event handlers. */
  connect(): Promise<void> {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return Promise.resolve();
    }

    return new Promise<void>((resolve, reject) => {
      const separator = this.wsUrl.includes("?") ? "&" : "?";
      const url = `${this.wsUrl}${separator}token=${encodeURIComponent(this.token)}`;

      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        resolve();
      };

      this.ws.onmessage = (evt) => {
        this.handleMessage(evt.data as string);
      };

      this.ws.onclose = () => {
        this.stopHeartbeat();
        this.reconnect();
      };

      this.ws.onerror = (err) => {
        reject(new Error("WebSocket connection failed"));
      };
    });
  }

  /** Gracefully close the connection. */
  disconnect(): void {
    this.stopHeartbeat();
    this.reconnectAttempts = this.maxReconnects; // prevent auto-reconnect
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /** Send a JSON-RPC request. Returns a generated id when none provided. */
  send(method: string, params: Record<string, any>, id?: string): string {
    const messageId = id ?? `req_${++this.nextId}`;
    const message: JsonRpcRequest = {
      jsonrpc: "2.0",
      method,
      params,
      id: messageId,
    };
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
    return messageId;
  }

  /** Register a handler for a server-pushed method. */
  on(method: string, handler: MessageHandler): void {
    this.handlers.set(method, handler);
  }

  // ---------------------------------------------------------------------------
  // Internal message handling
  // ---------------------------------------------------------------------------

  private handleMessage(data: string): void {
    try {
      const msg = JSON.parse(data) as JsonRpcRequest | JsonRpcResponse;

      // Server-pushed notification (no id) or request (has method)
      if ("method" in msg && msg.method) {
        const params = (msg.params ?? {}) as Record<string, unknown>;
        const handler = this.handlers.get(msg.method);
        if (handler) {
          handler(params);
        }
        if (this._messageCallback) {
          this._messageCallback(msg.method, params);
        }
        return;
      }

      // Response to a pending request
      if ("id" in msg && msg.id) {
        const pending = this.pendingRequests.get(msg.id);
        if (pending) {
          this.pendingRequests.delete(msg.id);
          const resp = msg as JsonRpcResponse;
          if (resp.error) {
            pending.reject(new Error(resp.error.message));
          } else {
            pending.resolve(resp.result);
          }
        }
      }
    } catch {
      // ignore malformed messages
    }
  }

  private reconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnects) return;
    this.reconnectAttempts++;
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 30_000);
    setTimeout(() => this.connect(), delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send("ping", {});
      }
    }, 30_000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval !== null) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  /** Register a callback for all incoming messages (raw dispatch). */
  onMessage(callback: (method: string, params: Record<string, unknown>) => void): void {
    this._messageCallback = callback;
  }

  private _messageCallback:
    | ((method: string, params: Record<string, unknown>) => void)
    | null = null;

  // ---------------------------------------------------------------------------
  // Convenience methods
  // ---------------------------------------------------------------------------

  /** Send a2ui.init with optional client info. Returns session on success. */
  sendInit(clientInfo: Record<string, unknown> = {}): Promise<A2UISession> {
    return new Promise((resolve, reject) => {
      const id = this.send("a2ui.init", clientInfo);
      this.pendingRequests.set(id, { resolve, reject });
    });
  }

  /** Alias for sendInit (backward compat). */
  init(): Promise<A2UISession> {
    return this.sendInit();
  }

  /** Respond to a user.requestInput prompt. */
  sendResponse(requestId: string, value: unknown): void {
    this.send("user.respond", { request_id: requestId, value });
  }

  /** Alias for sendResponse (backward compat). */
  respond(requestId: string, value: unknown): void {
    this.sendResponse(requestId, value);
  }

  /** Approve or reject a user.confirm dialog. */
  sendApproval(requestId: string, approved: boolean, reason?: string): void {
    this.send("user.approve", {
      request_id: requestId,
      approved,
      ...(reason !== undefined ? { reason } : {}),
    });
  }

  /** Alias for sendApproval (backward compat). */
  approve(requestId: string, approved: boolean, reason?: string): void {
    this.sendApproval(requestId, approved, reason);
  }

  /** Cancel a running task. */
  sendCancel(taskId: string): void {
    this.send("user.cancel", { task_id: taskId });
  }

  /** Alias for sendCancel (backward compat). */
  cancel(taskId: string): void {
    this.sendCancel(taskId);
  }
}
