import { useState, useCallback, useRef } from "react";
import type { ComposeResult, ChainAssignment, ChainTemplate, ChainExecution } from "../types/chain";
import {
  composeChain,
  createChainTemplate,
  executeChain,
  getChainExecution,
} from "../lib/api";

type ComposerPhase = "idle" | "composing" | "editing" | "saving" | "executing" | "done" | "error";

interface UseChainComposerResult {
  phase: ComposerPhase;
  error: string | null;
  composeResult: ComposeResult | null;
  editedAssignments: ChainAssignment[];
  editedName: string;
  editedBudget: number | null;
  savedTemplate: ChainTemplate | null;
  execution: ChainExecution | null;

  compose: (taskDescription: string, maxPrice?: number, minQuality?: number) => Promise<void>;
  setEditedName: (name: string) => void;
  setEditedBudget: (budget: number | null) => void;
  removeNode: (index: number) => void;
  reorderNode: (from: number, to: number) => void;
  replaceAgent: (index: number, agentId: string, agentName: string, rankScore: number) => void;
  saveTemplate: () => Promise<void>;
  executeTemplate: (inputData: Record<string, unknown>) => Promise<void>;
  reset: () => void;
}

export function useChainComposer(agentToken: string): UseChainComposerResult {
  const [phase, setPhase] = useState<ComposerPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [composeResult, setComposeResult] = useState<ComposeResult | null>(null);
  const [editedAssignments, setEditedAssignments] = useState<ChainAssignment[]>([]);
  const [editedName, setEditedName] = useState("");
  const [editedBudget, setEditedBudget] = useState<number | null>(null);
  const [savedTemplate, setSavedTemplate] = useState<ChainTemplate | null>(null);
  const [execution, setExecution] = useState<ChainExecution | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const compose = useCallback(async (
    taskDescription: string,
    maxPrice?: number,
    minQuality?: number,
  ) => {
    setPhase("composing");
    setError(null);
    try {
      const result = await composeChain(agentToken, {
        task_description: taskDescription,
        max_price: maxPrice,
        min_quality: minQuality,
      });
      setComposeResult(result);
      setEditedAssignments([...result.assignments]);
      setEditedName(result.name);
      setPhase("editing");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Compose failed");
      setPhase("error");
    }
  }, [agentToken]);

  const removeNode = useCallback((index: number) => {
    setEditedAssignments((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const reorderNode = useCallback((from: number, to: number) => {
    setEditedAssignments((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  }, []);

  const replaceAgent = useCallback((index: number, agentId: string, agentName: string, rankScore: number) => {
    setEditedAssignments((prev) =>
      prev.map((a, i) =>
        i === index ? { ...a, agent_id: agentId, agent_name: agentName, rank_score: rankScore } : a,
      ),
    );
  }, []);

  const buildGraphJson = useCallback((): string => {
    const nodes: Record<string, unknown> = {};
    let prevId: string | null = null;

    editedAssignments.forEach((assignment, i) => {
      const nodeId = `node_${assignment.capability}_${i}`;
      const nodeDef: Record<string, unknown> = {
        type: "agent_call",
        config: { agent_id: assignment.agent_id },
      };
      if (prevId) nodeDef.depends_on = [prevId];
      nodes[nodeId] = nodeDef;
      prevId = nodeId;
    });

    return JSON.stringify({ nodes, edges: [] });
  }, [editedAssignments]);

  const saveTemplate = useCallback(async () => {
    setPhase("saving");
    setError(null);
    try {
      const template = await createChainTemplate(agentToken, {
        name: editedName,
        description: composeResult?.description || "",
        category: composeResult?.category || "general",
        graph_json: buildGraphJson(),
        max_budget_usd: editedBudget ?? undefined,
      });
      setSavedTemplate(template);
      setPhase("done");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Save failed";
      setError(msg);
      // Stay in editing phase so user can retry
      setPhase("editing");
    }
  }, [agentToken, editedName, composeResult, buildGraphJson, editedBudget]);

  const executeTemplate = useCallback(async (inputData: Record<string, unknown>) => {
    if (!savedTemplate) return;
    setPhase("executing");
    setError(null);
    stopPolling();

    try {
      const exec = await executeChain(agentToken, savedTemplate.id, { input_data: inputData });
      setExecution(exec);

      // Poll for completion
      pollRef.current = setInterval(async () => {
        try {
          const updated = await getChainExecution(agentToken, exec.id);
          setExecution(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            stopPolling();
            setPhase("done");
          }
        } catch {
          stopPolling();
        }
      }, 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Execution failed");
      setPhase("error");
    }
  }, [agentToken, savedTemplate, stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setPhase("idle");
    setError(null);
    setComposeResult(null);
    setEditedAssignments([]);
    setEditedName("");
    setEditedBudget(null);
    setSavedTemplate(null);
    setExecution(null);
  }, [stopPolling]);

  return {
    phase, error,
    composeResult, editedAssignments, editedName, editedBudget,
    savedTemplate, execution,
    compose, setEditedName, setEditedBudget,
    removeNode, reorderNode, replaceAgent,
    saveTemplate, executeTemplate, reset,
  };
}
