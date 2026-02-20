import { useQuery, useMutation } from "@tanstack/react-query";

/* ── Types ── */

export interface WebMCPAction {
  id: string;
  title: string;
  description: string;
  price_per_execution: number;
  tags: string[];
  access_count: number;
  status: string;
  domain?: string;
  category?: string;
  created_at?: string;
}

export interface ActionListResponse {
  actions: WebMCPAction[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExecuteActionPayload {
  parameters: Record<string, unknown>;
  consent: boolean;
}

export interface ExecuteActionResponse {
  execution_id: string;
  status: string;
  result?: unknown;
}

export interface Execution {
  id: string;
  action_id: string;
  status: "completed" | "failed" | "executing" | "pending";
  amount: number;
  created_at: string;
  proof_verified?: boolean;
  result?: unknown;
}

export interface ExecutionListResponse {
  executions: Execution[];
  total: number;
  page: number;
  page_size: number;
}

/* ── Helpers ── */

const BASE_V3 = "/api/v3";

async function getV3<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(`${BASE_V3}${path}`, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

async function postV3<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_V3}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

/* ── Hooks ── */

export function useActions(
  q?: string,
  category?: string,
  maxPrice?: number,
  page = 1,
) {
  return useQuery({
    queryKey: ["webmcp-actions", q, category, maxPrice, page],
    queryFn: () =>
      getV3<ActionListResponse>("/webmcp/actions", {
        q: q || undefined,
        category: category || undefined,
        max_price: maxPrice,
        page,
        page_size: 12,
      }),
  });
}

export function useExecuteAction() {
  return useMutation({
    mutationFn: ({
      actionId,
      payload,
    }: {
      actionId: string;
      payload: ExecuteActionPayload;
    }) => postV3<ExecuteActionResponse>(`/webmcp/execute/${actionId}`, payload),
  });
}

export function useExecutions(page = 1) {
  return useQuery({
    queryKey: ["webmcp-executions", page],
    queryFn: () =>
      getV3<ExecutionListResponse>("/webmcp/executions", {
        page,
        page_size: 20,
      }),
  });
}
