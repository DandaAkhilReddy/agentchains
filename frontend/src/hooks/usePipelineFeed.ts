import { useState, useEffect, useCallback, useRef } from "react";
import { feed } from "../lib/ws";
import type { FeedEvent, AgentExecution, PipelineStep } from "../types/api";

/**
 * Subscribes to the marketplace WebSocket feed and reconstructs
 * agent execution pipelines from live events.
 */
export function usePipelineFeed() {
  const [executions, setExecutions] = useState<Map<string, AgentExecution>>(new Map());
  const [liveEvents, setLiveEvents] = useState<FeedEvent[]>([]);
  const stepCounter = useRef(0);

  const handleEvent = useCallback((event: FeedEvent) => {
    // Keep last 100 live events
    setLiveEvents((prev) => [event, ...prev].slice(0, 100));

    // Map events to pipeline steps
    const ev = event as unknown as Record<string, unknown>;
    const agentId = (ev.agent_id as string | undefined)
      ?? (ev.seller_id as string | undefined)
      ?? (ev.buyer_id as string | undefined)
      ?? "unknown";

    const agentName = (ev.agent_name as string | undefined) ?? agentId;

    const step: PipelineStep = {
      id: `step-${++stepCounter.current}`,
      agentId,
      agentName,
      action: event.type.replace(/_/g, " "),
      status: "completed",
      startedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      latencyMs: ev.delivery_ms as number | undefined,
      toolCall: {
        name: event.type,
        input: event as unknown as Record<string, unknown>,
      },
    };

    setExecutions((prev) => {
      const next = new Map(prev);
      const existing = next.get(agentId);
      if (existing) {
        next.set(agentId, {
          ...existing,
          steps: [...existing.steps, step].slice(-50),
          lastActivityAt: new Date().toISOString(),
          status: "active",
        });
      } else {
        next.set(agentId, {
          agentId,
          agentName,
          status: "active",
          steps: [step],
          startedAt: new Date().toISOString(),
          lastActivityAt: new Date().toISOString(),
        });
      }
      return next;
    });
  }, []);

  useEffect(() => {
    feed.connect();
    const unsub = feed.subscribe(handleEvent);
    return () => {
      unsub();
    };
  }, [handleEvent]);

  return {
    executions: Array.from(executions.values()),
    liveEvents,
    totalSteps: stepCounter.current,
  };
}
