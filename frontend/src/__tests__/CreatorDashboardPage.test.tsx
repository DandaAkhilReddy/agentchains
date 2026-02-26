import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CreatorDashboardPage from "../pages/CreatorDashboardPage";
import type { CreatorDashboard } from "../types/api";

/* ── Mock hooks ──────────────────────────────────────────────────────────── */

vi.mock("../hooks/useCreatorDashboard", () => ({
  useCreatorDashboard: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  claimAgent: vi.fn(),
}));

/* ── Mock AnimatedCounter to avoid requestAnimationFrame in jsdom ─────────── */

vi.mock("../components/AnimatedCounter", () => ({
  default: ({ value }: { value: number }) => (
    <span data-testid="animated-counter">{value}</span>
  ),
}));

/* ── Mock PageHeader and Badge to keep tests simple ─────────────────────── */

vi.mock("../components/PageHeader", () => ({
  default: ({ title, subtitle, actions }: { title: string; subtitle: string; actions?: React.ReactNode }) => (
    <div data-testid="page-header">
      <span data-testid="page-title">{title}</span>
      <span data-testid="page-subtitle">{subtitle}</span>
      {actions && <div data-testid="page-actions">{actions}</div>}
    </div>
  ),
}));

vi.mock("../components/Badge", () => ({
  default: ({ label }: { label: string }) => (
    <span data-testid="badge">{label}</span>
  ),
}));

vi.mock("../lib/format", () => ({
  formatUSD: (amount: number) => `$${amount.toFixed(2)}`,
}));

/* ── Import mocked modules after declarations ────────────────────────────── */

import { useCreatorDashboard } from "../hooks/useCreatorDashboard";
import { claimAgent } from "../lib/api";

const mockUseCreatorDashboard = vi.mocked(useCreatorDashboard);
const mockClaimAgent = vi.mocked(claimAgent);

/* ── Fixtures ────────────────────────────────────────────────────────────── */

const TOKEN = "test-token-abc";
const CREATOR_NAME = "Akhil";

const fullDashboard: CreatorDashboard = {
  creator_balance: 250.5,
  creator_total_earned: 1000.0,
  agents_count: 2,
  agents: [
    {
      agent_id: "agent-1",
      agent_name: "SalesBot",
      agent_type: "seller",
      status: "active",
      total_earned: 500.0,
      total_spent: 50.0,
      balance: 450.0,
    },
    {
      agent_id: "agent-2",
      agent_name: "BuyerBot",
      agent_type: "buyer",
      status: "inactive",
      total_earned: 200.0,
      total_spent: 100.0,
      balance: 100.0,
    },
  ],
  total_agent_earnings: 700.0,
  total_agent_spent: 150.0,
};

const emptyDashboard: CreatorDashboard = {
  creator_balance: 0,
  creator_total_earned: 0,
  agents_count: 0,
  agents: [],
  total_agent_earnings: 0,
  total_agent_spent: 0,
};

/* ── Helper ──────────────────────────────────────────────────────────────── */

interface RenderOptions {
  token?: string;
  creatorName?: string;
  onNavigate?: ReturnType<typeof vi.fn>;
  onLogout?: ReturnType<typeof vi.fn>;
}

function renderPage({
  token = TOKEN,
  creatorName = CREATOR_NAME,
  onNavigate = vi.fn(),
  onLogout = vi.fn(),
}: RenderOptions = {}) {
  return render(
    <CreatorDashboardPage
      token={token}
      creatorName={creatorName}
      onNavigate={onNavigate}
      onLogout={onLogout}
    />,
  );
}

/* ── Tests ───────────────────────────────────────────────────────────────── */

describe("CreatorDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: loaded with full data
    mockUseCreatorDashboard.mockReturnValue({
      data: fullDashboard,
      isLoading: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useCreatorDashboard>);
  });

  /* ── 1. Loading spinner ───────────────────────────────────────────────── */

  it("renders loading spinner when isLoading is true", () => {
    mockUseCreatorDashboard.mockReturnValue({
      data: undefined,
      isLoading: true,
      refetch: vi.fn(),
    } as ReturnType<typeof useCreatorDashboard>);

    renderPage();

    expect(screen.getByText("Loading dashboard...")).toBeInTheDocument();
    expect(screen.queryByTestId("page-header")).toBeNull();
  });

  /* ── 2. Renders dashboard with agents ────────────────────────────────── */

  it("renders dashboard with agents", () => {
    renderPage();

    expect(screen.getByTestId("page-header")).toBeInTheDocument();
    expect(screen.getByText("Creator Studio")).toBeInTheDocument();
    expect(screen.getByText(`Welcome back, ${CREATOR_NAME}`)).toBeInTheDocument();

    // Both agent names appear
    expect(screen.getByText("SalesBot")).toBeInTheDocument();
    expect(screen.getByText("BuyerBot")).toBeInTheDocument();

    // Empty state should NOT appear
    expect(screen.queryByText("No agents linked yet")).toBeNull();
  });

  /* ── 3. Renders empty agents state ───────────────────────────────────── */

  it("renders empty agents state when no agents", () => {
    mockUseCreatorDashboard.mockReturnValue({
      data: emptyDashboard,
      isLoading: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useCreatorDashboard>);

    renderPage();

    expect(screen.getByText("No agents linked yet")).toBeInTheDocument();
    expect(screen.getByText("Claim your first agent below to get started")).toBeInTheDocument();
    expect(screen.queryByText("SalesBot")).toBeNull();
  });

  /* ── 4. Success claim message shown in green ─────────────────────────── */

  it("shows success claim message in green", async () => {
    const refetch = vi.fn();
    mockUseCreatorDashboard.mockReturnValue({
      data: fullDashboard,
      isLoading: false,
      refetch,
    } as ReturnType<typeof useCreatorDashboard>);
    mockClaimAgent.mockResolvedValueOnce(undefined);

    renderPage();

    const input = screen.getByPlaceholderText("Agent ID (UUID)");
    fireEvent.change(input, { target: { value: "agent-uuid-123" } });

    const claimBtn = screen.getByRole("button", { name: /claim/i });
    fireEvent.click(claimBtn);

    await waitFor(() => {
      expect(screen.getByText("Agent linked successfully!")).toBeInTheDocument();
    });

    const msgEl = screen.getByText("Agent linked successfully!");
    expect(msgEl).toHaveStyle({ color: "#34d399" });
    expect(refetch).toHaveBeenCalled();
    // Input is cleared after success
    expect((input as HTMLInputElement).value).toBe("");
  });

  /* ── 5. Error claim message shown in red ─────────────────────────────── */

  it("shows error claim message in red", async () => {
    mockClaimAgent.mockRejectedValueOnce(new Error("Agent not found"));

    renderPage();

    const input = screen.getByPlaceholderText("Agent ID (UUID)");
    fireEvent.change(input, { target: { value: "bad-uuid" } });

    fireEvent.click(screen.getByRole("button", { name: /claim/i }));

    await waitFor(() => {
      expect(screen.getByText("Agent not found")).toBeInTheDocument();
    });

    const msgEl = screen.getByText("Agent not found");
    expect(msgEl).toHaveStyle({ color: "#f87171" });
  });

  /* ── 6. Claim with empty id does nothing ─────────────────────────────── */

  it("claim with empty id does nothing", async () => {
    renderPage();

    // Input is empty — button is disabled but we test the guard anyway
    const input = screen.getByPlaceholderText("Agent ID (UUID)");
    expect((input as HTMLInputElement).value).toBe("");

    // Directly fire click on an empty input to exercise the early-return guard
    // (the button is disabled, but the handler checks claimId.trim() itself)
    fireEvent.click(screen.getByRole("button", { name: /claim/i }));

    // claimAgent must not be called
    await waitFor(() => {
      expect(mockClaimAgent).not.toHaveBeenCalled();
    });

    // No message should appear
    expect(screen.queryByText("Agent linked successfully!")).toBeNull();
  });

  /* ── 7. Whitespace-only id does nothing ──────────────────────────────── */

  it("claim with whitespace-only id does nothing", async () => {
    renderPage();

    const input = screen.getByPlaceholderText("Agent ID (UUID)");
    fireEvent.change(input, { target: { value: "   " } });

    // Manually invoke handler by simulating button click
    // Note: the button has disabled={!claimId.trim()}, so we bypass with fireEvent
    const claimBtn = screen.getByRole("button", { name: /claim/i });
    fireEvent.click(claimBtn);

    await waitFor(() => {
      expect(mockClaimAgent).not.toHaveBeenCalled();
    });
  });

  /* ── 8. Withdraw button calls onNavigate('redeem') ───────────────────── */

  it("Withdraw button calls onNavigate('redeem')", () => {
    const onNavigate = vi.fn();
    renderPage({ onNavigate });

    fireEvent.click(screen.getByText("Withdraw"));
    expect(onNavigate).toHaveBeenCalledWith("redeem");
  });

  /* ── 9. Logout button calls onLogout ─────────────────────────────────── */

  it("Logout button calls onLogout", () => {
    const onLogout = vi.fn();
    renderPage({ onLogout });

    // The logout button contains a LogOut icon — find by role
    const logoutBtns = screen.getAllByRole("button");
    // The logout button is the one without text content (icon-only)
    const logoutBtn = logoutBtns.find((btn) => btn.querySelector("svg") && btn.textContent?.trim() === "");
    expect(logoutBtn).toBeDefined();
    fireEvent.click(logoutBtn!);
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  /* ── 10. AnimatedCounter used for isAnimated stat cards ─────────────── */

  it("AnimatedCounter used for isAnimated stat cards", () => {
    renderPage();

    // "Active Agents" card has isAnimated: true and value = agents_count = 2
    const counters = screen.getAllByTestId("animated-counter");
    expect(counters).toHaveLength(1);
    expect(counters[0]).toHaveTextContent("2");
  });

  /* ── 11. Non-animated stat cards render plain text ───────────────────── */

  it("non-animated stat cards render plain text values", () => {
    renderPage();

    // These are rendered without AnimatedCounter
    // formatUSD(250.5) → "$250.50" (our mock)
    expect(screen.getByText("$250.50")).toBeInTheDocument();
    // formatUSD(1000.0) → "$1000.00"
    expect(screen.getByText("$1000.00")).toBeInTheDocument();
  });

  /* ── 12. claimAgent error without message uses fallback ─────────────── */

  it("uses fallback error message when error has no message property", async () => {
    mockClaimAgent.mockRejectedValueOnce({});

    renderPage();

    const input = screen.getByPlaceholderText("Agent ID (UUID)");
    fireEvent.change(input, { target: { value: "some-id" } });
    fireEvent.click(screen.getByRole("button", { name: /claim/i }));

    await waitFor(() => {
      expect(screen.getByText("Failed to claim agent")).toBeInTheDocument();
    });

    const msgEl = screen.getByText("Failed to claim agent");
    expect(msgEl).toHaveStyle({ color: "#f87171" });
  });

  /* ── 13. Agent avatar shows first 2 chars uppercased ────────────────── */

  it("agent avatar shows first 2 chars of agent name uppercased", () => {
    renderPage();

    // "SalesBot" → "SA", "BuyerBot" → "BU"
    expect(screen.getByText("SA")).toBeInTheDocument();
    expect(screen.getByText("BU")).toBeInTheDocument();
  });

  /* ── 14. Agent badges render type and status ─────────────────────────── */

  it("renders agent type and status badges for each agent", () => {
    renderPage();

    const badges = screen.getAllByTestId("badge");
    const badgeLabels = badges.map((b) => b.textContent);

    expect(badgeLabels).toContain("seller");
    expect(badgeLabels).toContain("active");
    expect(badgeLabels).toContain("buyer");
    expect(badgeLabels).toContain("inactive");
  });

  /* ── 15. Input value updates on change ───────────────────────────────── */

  it("updates claim input value on change", () => {
    renderPage();

    const input = screen.getByPlaceholderText("Agent ID (UUID)") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "my-agent-id" } });
    expect(input.value).toBe("my-agent-id");
  });

  /* ── 16. Claim trims the agent ID before sending ─────────────────────── */

  it("trims leading/trailing whitespace from agent ID when claiming", async () => {
    mockClaimAgent.mockResolvedValueOnce(undefined);

    renderPage();

    const input = screen.getByPlaceholderText("Agent ID (UUID)");
    fireEvent.change(input, { target: { value: "  trimmed-id  " } });
    fireEvent.click(screen.getByRole("button", { name: /claim/i }));

    await waitFor(() => {
      expect(mockClaimAgent).toHaveBeenCalledWith(TOKEN, "trimmed-id");
    });
  });

  /* ── 17. Dashboard renders without crash when data is undefined ───────── */

  it("renders without crash when dashboard data is undefined (non-loading)", () => {
    mockUseCreatorDashboard.mockReturnValue({
      data: undefined,
      isLoading: false,
      refetch: vi.fn(),
    } as ReturnType<typeof useCreatorDashboard>);

    renderPage();

    // Should fall through to the loaded state with zero/default values
    expect(screen.getByTestId("page-header")).toBeInTheDocument();
    // No agents → shows empty state
    expect(screen.getByText("No agents linked yet")).toBeInTheDocument();
  });
});
