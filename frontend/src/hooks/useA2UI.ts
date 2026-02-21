import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { A2UIClient } from "../lib/a2ui";
import type {
  A2UISession,
  A2UIComponent,
  A2UIRenderMessage,
  A2UIUpdateMessage,
  A2UIRequestInputMessage,
  A2UIConfirmMessage,
  A2UIProgressMessage,
  A2UINavigateMessage,
  A2UINotifyMessage,
} from "../types/a2ui";

export interface UseA2UIReturn {
  session: A2UISession | null;
  components: A2UIComponent[];
  activeInput: A2UIRequestInputMessage | null;
  activeConfirm: A2UIConfirmMessage | null;
  progress: Map<string, A2UIProgressMessage>;
  notifications: A2UINotifyMessage[];
  connect: () => Promise<void>;
  disconnect: () => void;
  respond: (requestId: string, value: unknown) => void;
  approve: (requestId: string, approved: boolean, reason?: string) => void;
  cancel: (taskId: string) => void;
}

/**
 * React hook for managing an A2UI WebSocket session with an agent.
 *
 * Manages the A2UIClient lifecycle, tracks components map (id -> A2UIComponent),
 * and handles all incoming UI methods:
 *   ui.render, ui.update, ui.request_input, ui.confirm,
 *   ui.progress, ui.navigate, ui.notify
 *
 * Returns state objects and action functions for the consumer.
 */
export function useA2UI(agentId: string, token: string): UseA2UIReturn {
  const clientRef = useRef<A2UIClient | null>(null);
  const [session, setSession] = useState<A2UISession | null>(null);
  const [componentsMap, setComponentsMap] = useState<Map<string, A2UIComponent>>(
    () => new Map(),
  );
  const [activeInput, setActiveInput] = useState<A2UIRequestInputMessage | null>(null);
  const [activeConfirm, setActiveConfirm] = useState<A2UIConfirmMessage | null>(null);
  const [progress, setProgress] = useState<Map<string, A2UIProgressMessage>>(
    () => new Map(),
  );
  const [notifications, setNotifications] = useState<A2UINotifyMessage[]>([]);

  // Derive the base URL from the current window location
  const baseUrl = useMemo(() => {
    const proto = window.location.protocol;
    return `${proto}//${window.location.host}`;
  }, []);

  // Create or re-create the client when agentId/token changes
  useEffect(() => {
    const client = new A2UIClient(baseUrl, token);
    clientRef.current = client;

    // ── Register handlers for server-pushed A2UI methods ──

    client.on("ui.render", (params) => {
      const msg = params as unknown as A2UIRenderMessage;
      setComponentsMap((prev) => {
        const next = new Map(prev);
        next.set(msg.component_id, {
          component_id: msg.component_id,
          component_type: msg.component_type,
          data: msg.data,
          metadata: msg.metadata,
        });
        return next;
      });
    });

    client.on("ui.update", (params) => {
      const msg = params as unknown as A2UIUpdateMessage;
      setComponentsMap((prev) => {
        const existing = prev.get(msg.component_id);
        if (!existing) return prev;

        const next = new Map(prev);
        let updatedData: Record<string, unknown>;

        switch (msg.operation) {
          case "replace":
            updatedData = msg.data;
            break;
          case "merge":
            updatedData = { ...existing.data, ...msg.data };
            break;
          case "append": {
            updatedData = { ...existing.data };
            for (const [key, val] of Object.entries(msg.data)) {
              const existingVal = existing.data[key];
              if (Array.isArray(existingVal) && Array.isArray(val)) {
                updatedData[key] = [...existingVal, ...val];
              } else if (typeof existingVal === "string" && typeof val === "string") {
                updatedData[key] = existingVal + val;
              } else {
                updatedData[key] = val;
              }
            }
            break;
          }
          default:
            updatedData = msg.data;
        }

        next.set(msg.component_id, { ...existing, data: updatedData });
        return next;
      });
    });

    client.on("ui.request_input", (params) => {
      setActiveInput(params as unknown as A2UIRequestInputMessage);
    });

    client.on("ui.confirm", (params) => {
      setActiveConfirm(params as unknown as A2UIConfirmMessage);
    });

    client.on("ui.progress", (params) => {
      const msg = params as unknown as A2UIProgressMessage;
      setProgress((prev) => {
        const next = new Map(prev);
        next.set(msg.task_id, msg);
        return next;
      });
    });

    client.on("ui.navigate", (params) => {
      const msg = params as unknown as A2UINavigateMessage;
      if (msg.new_tab) {
        window.open(msg.url, "_blank", "noopener,noreferrer");
      } else {
        window.location.href = msg.url;
      }
    });

    client.on("ui.notify", (params) => {
      const msg = params as unknown as A2UINotifyMessage;
      setNotifications((prev) => [...prev, msg]);

      // Auto-dismiss after duration
      const duration = msg.duration_ms ?? 5000;
      if (duration > 0) {
        setTimeout(() => {
          setNotifications((prev) => prev.filter((n) => n !== msg));
        }, duration);
      }
    });

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [agentId, token, baseUrl]);

  // ── User action helpers ──

  const connect = useCallback(async () => {
    const client = clientRef.current;
    if (!client) return;

    await client.connect();
    const sess = await client.sendInit({ agent_id: agentId });
    setSession({
      ...sess,
      status: "connected",
    });
  }, [agentId]);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
    setSession((prev) =>
      prev ? { ...prev, status: "disconnected" } : null,
    );
  }, []);

  const respond = useCallback((requestId: string, value: unknown) => {
    clientRef.current?.sendResponse(requestId, value);
    setActiveInput(null);
  }, []);

  const approve = useCallback(
    (requestId: string, approved: boolean, reason?: string) => {
      clientRef.current?.sendApproval(requestId, approved, reason);
      setActiveConfirm(null);
    },
    [],
  );

  const cancel = useCallback((taskId: string) => {
    clientRef.current?.sendCancel(taskId);
  }, []);

  // Convert map to ordered array for consumers
  const components = useMemo(
    () => Array.from(componentsMap.values()),
    [componentsMap],
  );

  return {
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
    cancel,
  };
}
