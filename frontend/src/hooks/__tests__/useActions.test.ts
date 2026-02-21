import { describe, expect, test, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import {
  useActions,
  useExecuteAction,
  useExecutions,
} from "../useActions";
import type {
  ActionListResponse,
  ExecuteActionResponse,
  ExecutionListResponse,
} from "../useActions";
import { createWrapper } from "../../test/test-utils";

/* ── Fetch mock helper ── */

function mockFetchSuccess(data: unknown) {
  (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  });
}

function mockFetchError(status: number, body: string) {
  (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(body),
  });
}

function mockFetchNeverResolves() {
  (global.fetch as ReturnType<typeof vi.fn>).mockReturnValueOnce(
    new Promise(() => {}),
  );
}

/* ── Fixtures ── */

const actionsResponse: ActionListResponse = {
  actions: [
    {
      id: "act-1",
      title: "Summarise PDF",
      description: "Summarises a PDF document",
      price_per_execution: 0.05,
      tags: ["pdf", "summary"],
      access_count: 120,
      status: "active",
      domain: "documents",
      category: "productivity",
      created_at: "2026-01-10T00:00:00Z",
    },
    {
      id: "act-2",
      title: "Translate Text",
      description: "Translates text between languages",
      price_per_execution: 0.02,
      tags: ["translate", "nlp"],
      access_count: 450,
      status: "active",
      category: "language",
      created_at: "2026-01-15T00:00:00Z",
    },
  ],
  total: 2,
  page: 1,
  page_size: 12,
};

const emptyActionsResponse: ActionListResponse = {
  actions: [],
  total: 0,
  page: 1,
  page_size: 12,
};

const executeResponse: ExecuteActionResponse = {
  execution_id: "exec-abc",
  status: "completed",
  result: { summary: "done" },
};

const executionsResponse: ExecutionListResponse = {
  executions: [
    {
      id: "exec-1",
      action_id: "act-1",
      status: "completed",
      amount: 0.05,
      created_at: "2026-02-01T10:00:00Z",
      proof_verified: true,
      result: { ok: true },
    },
    {
      id: "exec-2",
      action_id: "act-2",
      status: "failed",
      amount: 0.02,
      created_at: "2026-02-02T12:00:00Z",
      proof_verified: false,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

const emptyExecutionsResponse: ExecutionListResponse = {
  executions: [],
  total: 0,
  page: 1,
  page_size: 20,
};

/* ── Tests ── */

beforeEach(() => {
  global.fetch = vi.fn();
  vi.clearAllMocks();
});

// ─────────────────────────────────────────
// useActions
// ─────────────────────────────────────────

describe("useActions", () => {
  test("returns loading state initially", () => {
    mockFetchNeverResolves();

    const { result } = renderHook(() => useActions(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns actions list on success", async () => {
    mockFetchSuccess(actionsResponse);

    const { result } = renderHook(() => useActions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(actionsResponse);
    expect(result.current.data?.actions).toHaveLength(2);
    expect(result.current.data?.total).toBe(2);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    mockFetchError(500, "Internal Server Error");

    const { result } = renderHook(() => useActions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(
      "API 500: Internal Server Error",
    );
    expect(result.current.data).toBeUndefined();
  });

  test("handles empty list", async () => {
    mockFetchSuccess(emptyActionsResponse);

    const { result } = renderHook(() => useActions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.actions).toHaveLength(0);
    expect(result.current.data?.total).toBe(0);
  });

  test("query key is correct", async () => {
    mockFetchSuccess(actionsResponse);
    mockFetchSuccess(emptyActionsResponse);

    const wrapper = createWrapper();

    const { result, rerender } = renderHook(
      ({ q, category, maxPrice, page }) =>
        useActions(q, category, maxPrice, page),
      {
        wrapper,
        initialProps: {
          q: "pdf" as string | undefined,
          category: "productivity" as string | undefined,
          maxPrice: 1 as number | undefined,
          page: 1,
        },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // First call should include q, category, max_price, page, page_size params
    const firstCallUrl = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as string;
    expect(firstCallUrl).toContain("/api/v3/webmcp/actions");
    expect(firstCallUrl).toContain("q=pdf");
    expect(firstCallUrl).toContain("category=productivity");

    // Changing params triggers a new fetch because the query key changes
    rerender({
      q: "translate",
      category: undefined,
      maxPrice: undefined,
      page: 2,
    });

    await waitFor(() =>
      expect(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length,
      ).toBeGreaterThanOrEqual(2),
    );
  });

  test("passes filter and pagination parameters in URL", async () => {
    mockFetchSuccess(actionsResponse);

    renderHook(() => useActions("search-term", "ai", 5, 3), {
      wrapper: createWrapper(),
    });

    await waitFor(() =>
      expect(global.fetch as ReturnType<typeof vi.fn>).toHaveBeenCalled(),
    );

    const url = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as string;
    expect(url).toContain("q=search-term");
    expect(url).toContain("category=ai");
    expect(url).toContain("max_price=5");
    expect(url).toContain("page=3");
    expect(url).toContain("page_size=12");
  });

  test("omits undefined optional parameters from URL", async () => {
    mockFetchSuccess(actionsResponse);

    renderHook(() => useActions(undefined, undefined, undefined, 1), {
      wrapper: createWrapper(),
    });

    await waitFor(() =>
      expect(global.fetch as ReturnType<typeof vi.fn>).toHaveBeenCalled(),
    );

    const url = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as string;
    expect(url).not.toContain("q=");
    expect(url).not.toContain("category=");
    expect(url).toContain("page=1");
    expect(url).toContain("page_size=12");
  });
});

// ─────────────────────────────────────────
// useExecuteAction
// ─────────────────────────────────────────

describe("useExecuteAction", () => {
  test("mutation function works and returns response", async () => {
    mockFetchSuccess(executeResponse);

    const { result } = renderHook(() => useExecuteAction(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      result.current.mutate({
        actionId: "act-1",
        payload: { parameters: { lang: "en" }, consent: true },
      });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(executeResponse);
  });

  test("handles success callback", async () => {
    mockFetchSuccess(executeResponse);
    const onSuccess = vi.fn();

    const { result } = renderHook(
      () => useExecuteAction(),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.mutate(
        {
          actionId: "act-1",
          payload: { parameters: {}, consent: true },
        },
        { onSuccess },
      );
    });

    await waitFor(() => expect(onSuccess).toHaveBeenCalled());

    const call = onSuccess.mock.calls[0];
    expect(call[0]).toEqual(executeResponse);
    expect(call[1]).toEqual(
      expect.objectContaining({ actionId: "act-1" }),
    );
  });

  test("handles error callback", async () => {
    mockFetchError(400, "Bad Request");
    const onError = vi.fn();

    const { result } = renderHook(
      () => useExecuteAction(),
      { wrapper: createWrapper() },
    );

    await act(async () => {
      result.current.mutate(
        {
          actionId: "act-1",
          payload: { parameters: {}, consent: false },
        },
        { onError },
      );
    });

    await waitFor(() => expect(onError).toHaveBeenCalled());

    const errorArg = onError.mock.calls[0][0] as Error;
    expect(errorArg.message).toBe("API 400: Bad Request");
  });

  test("passes correct parameters to fetch", async () => {
    mockFetchSuccess(executeResponse);

    const { result } = renderHook(() => useExecuteAction(), {
      wrapper: createWrapper(),
    });

    const payload = {
      parameters: { file_url: "https://example.com/doc.pdf" },
      consent: true,
    };

    await act(async () => {
      result.current.mutate({ actionId: "act-99", payload });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v3/webmcp/execute/act-99");
    expect(options.method).toBe("POST");
    expect(options.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(options.body)).toEqual(payload);
  });

  test("shows loading state during execution", async () => {
    // Use a promise we control to hold the mutation in-flight
    let resolveFetch!: (value: unknown) => void;
    (global.fetch as ReturnType<typeof vi.fn>).mockReturnValueOnce(
      new Promise((resolve) => {
        resolveFetch = resolve;
      }),
    );

    const { result } = renderHook(() => useExecuteAction(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    act(() => {
      result.current.mutate({
        actionId: "act-1",
        payload: { parameters: {}, consent: true },
      });
    });

    await waitFor(() => expect(result.current.isPending).toBe(true));

    // Resolve the fetch to finish the mutation
    await act(async () => {
      resolveFetch({
        ok: true,
        json: () => Promise.resolve(executeResponse),
        text: () => Promise.resolve(""),
      });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.isPending).toBe(false);
  });
});

// ─────────────────────────────────────────
// useExecutions
// ─────────────────────────────────────────

describe("useExecutions", () => {
  test("returns loading state initially", () => {
    mockFetchNeverResolves();

    const { result } = renderHook(() => useExecutions(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBe(null);
  });

  test("returns execution history on success", async () => {
    mockFetchSuccess(executionsResponse);

    const { result } = renderHook(() => useExecutions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(executionsResponse);
    expect(result.current.data?.executions).toHaveLength(2);
    expect(result.current.data?.total).toBe(2);
    expect(result.current.error).toBe(null);
  });

  test("handles error state", async () => {
    mockFetchError(503, "Service Unavailable");

    const { result } = renderHook(() => useExecutions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeTruthy();
    expect((result.current.error as Error).message).toBe(
      "API 503: Service Unavailable",
    );
    expect(result.current.data).toBeUndefined();
  });

  test("handles empty results", async () => {
    mockFetchSuccess(emptyExecutionsResponse);

    const { result } = renderHook(() => useExecutions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.executions).toHaveLength(0);
    expect(result.current.data?.total).toBe(0);
  });

  test("passes page parameter in URL", async () => {
    mockFetchSuccess(executionsResponse);

    renderHook(() => useExecutions(3), {
      wrapper: createWrapper(),
    });

    await waitFor(() =>
      expect(global.fetch as ReturnType<typeof vi.fn>).toHaveBeenCalled(),
    );

    const url = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as string;
    expect(url).toContain("/api/v3/webmcp/executions");
    expect(url).toContain("page=3");
    expect(url).toContain("page_size=20");
  });

  test("query key includes page so different pages are cached separately", async () => {
    mockFetchSuccess(executionsResponse);
    mockFetchSuccess(emptyExecutionsResponse);

    const wrapper = createWrapper();

    const { result, rerender } = renderHook(
      ({ page }) => useExecutions(page),
      {
        wrapper,
        initialProps: { page: 1 },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(executionsResponse);

    // Changing page triggers a new fetch (different query key)
    rerender({ page: 2 });

    await waitFor(() =>
      expect(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls.length,
      ).toBeGreaterThanOrEqual(2),
    );

    const secondUrl = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[1][0] as string;
    expect(secondUrl).toContain("page=2");
  });
});
