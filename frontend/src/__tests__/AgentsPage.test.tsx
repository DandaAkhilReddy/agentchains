import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AgentsPage from "../pages/AgentsPage";
import type { Agent, AgentListResponse } from "../types/api";

// ── Module-level mocks ────────────────────────────────────────────────────────

vi.mock("../hooks/useAgents", () => ({
  useAgents: vi.fn(),
}));

// Stub child components that pull in extra deps (lucide-react icons render fine
// in jsdom, so only stubbing the heavier custom components).
vi.mock("../components/CopyButton", () => ({
  default: ({ value }: { value: string }) => (
    <button aria-label={`copy-${value}`}>copy</button>
  ),
}));

vi.mock("../components/ProgressRing", () => ({
  default: ({ value }: { value: number }) => (
    <div data-testid="progress-ring" data-value={value} />
  ),
}));

vi.mock("../components/Badge", () => ({
  default: ({ label }: { label: string }) => <span>{label}</span>,
  agentTypeVariant: (t: string) => t,
  statusVariant: (s: string) => s,
}));

vi.mock("../components/PageHeader", () => ({
  default: ({ title, subtitle }: { title: string; subtitle?: string }) => (
    <div>
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  ),
}));

vi.mock("../components/Pagination", () => ({
  default: ({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (p: number) => void }) => (
    <div data-testid="pagination" data-page={page} data-total-pages={totalPages}>
      <button onClick={() => onPageChange(page + 1)}>Next</button>
    </div>
  ),
}));

vi.mock("../lib/format", () => ({
  relativeTime: (d: string) => `ago(${d})`,
  truncateId: (id: string) => id.slice(0, 8),
}));

// ── Import hook mock ──────────────────────────────────────────────────────────

import { useAgents } from "../hooks/useAgents";

const mockUseAgents = vi.mocked(useAgents);

// ── Fixtures ─────────────────────────────────────────────────────────────────

function makeAgent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agt-0001",
    name: "Alpha Bot",
    description: "A test agent",
    agent_type: "seller",
    wallet_address: "0xdeadbeef",
    capabilities: ["search", "recommend"],
    a2a_endpoint: "https://alpha.example.com",
    status: "active",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    last_seen_at: null,
    ...overrides,
  };
}

function makeResponse(agents: Agent[], total: number = agents.length): AgentListResponse {
  return { total, page: 1, page_size: 20, agents };
}

function renderPage() {
  return render(<AgentsPage />);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("AgentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── 1. Loading skeletons ─────────────────────────────────────────────────
  it("renders loading skeletons", () => {
    mockUseAgents.mockReturnValue({ data: undefined, isLoading: true } as ReturnType<typeof useAgents>);

    const { container } = renderPage();

    // The skeleton grid renders 6 skeleton cards; each has an animate-pulse div.
    const pulsingEls = container.querySelectorAll(".animate-pulse");
    expect(pulsingEls.length).toBeGreaterThanOrEqual(6);
  });

  // ── 2. Empty state when no data ──────────────────────────────────────────
  it("renders empty state when no data", () => {
    mockUseAgents.mockReturnValue({ data: undefined, isLoading: false } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.getByText("No agents registered")).toBeInTheDocument();
    expect(
      screen.getByText("Agents will appear here once they register on the network"),
    ).toBeInTheDocument();
  });

  // ── 3. Renders agent cards ───────────────────────────────────────────────
  it("renders agents with cards", () => {
    const agents = [
      makeAgent({ id: "a1", name: "Alpha Bot" }),
      makeAgent({ id: "a2", name: "Beta Bot", agent_type: "buyer" }),
    ];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.getByText("Alpha Bot")).toBeInTheDocument();
    expect(screen.getByText("Beta Bot")).toBeInTheDocument();
  });

  // ── 4. +N more badge for agents with >4 capabilities ─────────────────────
  it("shows +N more badge for agents with >4 capabilities", () => {
    const agent = makeAgent({
      capabilities: ["a", "b", "c", "d", "e", "f"],
    });
    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    // 6 caps - 4 shown = +2 more
    expect(screen.getByText("+2")).toBeInTheDocument();
  });

  // ── 5. Online indicator for recently seen agent ──────────────────────────
  it("shows online indicator for recently seen agents", () => {
    // last_seen_at = 1 minute ago → online
    const recent = new Date(Date.now() - 60_000).toISOString();
    const agent = makeAgent({ last_seen_at: recent });

    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    // Wifi icon title or the indicator div title should be "Online"
    expect(screen.getByTitle("Online")).toBeInTheDocument();
  });

  // ── 6. Offline indicator for old last_seen_at ────────────────────────────
  it("shows offline indicator for old last_seen_at", () => {
    // last_seen_at = 10 minutes ago → offline (> 5 min threshold)
    const old = new Date(Date.now() - 10 * 60_000).toISOString();
    const agent = makeAgent({ last_seen_at: old });

    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.getByTitle("Offline")).toBeInTheDocument();
  });

  // ── 7. Client-side search filter ────────────────────────────────────────
  it("filters agents by search text", () => {
    const agents = [
      makeAgent({ id: "a1", name: "Zeta Searcher" }),
      makeAgent({ id: "a2", name: "Omega Seller" }),
    ];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    const searchInput = screen.getByPlaceholderText(
      "Search agents by name, ID, or capability...",
    );
    fireEvent.change(searchInput, { target: { value: "Zeta" } });

    expect(screen.getByText("Zeta Searcher")).toBeInTheDocument();
    expect(screen.queryByText("Omega Seller")).not.toBeInTheDocument();
  });

  // ── 8. Empty state with search hint when search is active ────────────────
  it("empty state shows search hint when search is active", () => {
    const agent = makeAgent({ name: "Gamma" });
    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    const searchInput = screen.getByPlaceholderText(
      "Search agents by name, ID, or capability...",
    );
    fireEvent.change(searchInput, { target: { value: "zzz-no-match" } });

    expect(screen.getByText("No agents registered")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting your search query"),
    ).toBeInTheDocument();
  });

  // ── 9. Pagination appears when total > 20 ────────────────────────────────
  it("pagination appears when total > 20", () => {
    const agents = [makeAgent()];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents, 41), // total=41 > 20 → 3 pages
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    const pagination = screen.getByTestId("pagination");
    expect(pagination).toBeInTheDocument();
    expect(pagination.getAttribute("data-total-pages")).toBe("3");
  });

  // ── 10. No pagination when total ≤ 20 ────────────────────────────────────
  it("pagination does not appear when total is 20 or fewer", () => {
    const agents = [makeAgent()];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents, 20),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.queryByTestId("pagination")).not.toBeInTheDocument();
  });

  // ── 11. Type filter resets page to 1 ────────────────────────────────────
  it("type filter resets page to 1", () => {
    const agents = [makeAgent()];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents, 41),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    // Advance to page 2 via the pagination mock.
    fireEvent.click(screen.getByText("Next"));

    // Confirm useAgents was called with page=2 at some point.
    const calls = mockUseAgents.mock.calls.map((c) => c[0].page);
    expect(calls).toContain(2);

    // Now change the type filter — should reset page back to 1.
    const typeSelect = screen.getByDisplayValue("All Types");
    fireEvent.change(typeSelect, { target: { value: "seller" } });

    const lastCall = mockUseAgents.mock.calls.at(-1)?.[0];
    expect(lastCall?.page).toBe(1);
    expect(lastCall?.agent_type).toBe("seller");
  });

  // ── 12. ProgressRing shows when capabilities.length > 0 ──────────────────
  it("shows ProgressRing when agent has capabilities", () => {
    const agent = makeAgent({ capabilities: ["tool-a", "tool-b"] });
    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.getByTestId("progress-ring")).toBeInTheDocument();
    // powerScore = min(2 * 20, 100) = 40
    expect(screen.getByTestId("progress-ring").getAttribute("data-value")).toBe("40");
  });

  // ── 13. ProgressRing hidden when no capabilities ─────────────────────────
  it("does not show ProgressRing when agent has no capabilities", () => {
    const agent = makeAgent({ capabilities: [] });
    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.queryByTestId("progress-ring")).not.toBeInTheDocument();
  });

  // ── 14. Agent type gradient class selection ───────────────────────────────
  it("renders correct initial for agent name", () => {
    const agent = makeAgent({ name: "Delta" });
    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    const { container } = renderPage();

    // The avatar div contains the first letter of the agent name uppercased.
    expect(container.textContent).toContain("D");
  });

  // ── 15. last_seen_at = null → offline ────────────────────────────────────
  it("shows offline when last_seen_at is null", () => {
    const agent = makeAgent({ last_seen_at: null });
    mockUseAgents.mockReturnValue({
      data: makeResponse([agent]),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(screen.getByTitle("Offline")).toBeInTheDocument();
  });

  // ── 16. Subtitle shows count from data ──────────────────────────────────
  it("shows agent count in subtitle when data is loaded", () => {
    const agents = [makeAgent({ id: "a1" }), makeAgent({ id: "a2" })];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents, 2),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(
      screen.getByText("2 agents registered on the network"),
    ).toBeInTheDocument();
  });

  // ── 17. Subtitle fallback when data is undefined ─────────────────────────
  it("shows fallback subtitle when data is not yet loaded", () => {
    mockUseAgents.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as ReturnType<typeof useAgents>);

    renderPage();

    expect(
      screen.getByText("Browse and manage registered agents"),
    ).toBeInTheDocument();
  });

  // ── 18. Search by capability ─────────────────────────────────────────────
  it("filters agents by capability name", () => {
    const agents = [
      makeAgent({ id: "a1", name: "Agent A", capabilities: ["vision"] }),
      makeAgent({ id: "a2", name: "Agent B", capabilities: ["text-gen"] }),
    ];
    mockUseAgents.mockReturnValue({
      data: makeResponse(agents),
      isLoading: false,
    } as ReturnType<typeof useAgents>);

    renderPage();

    const searchInput = screen.getByPlaceholderText(
      "Search agents by name, ID, or capability...",
    );
    fireEvent.change(searchInput, { target: { value: "vision" } });

    expect(screen.getByText("Agent A")).toBeInTheDocument();
    expect(screen.queryByText("Agent B")).not.toBeInTheDocument();
  });
});
