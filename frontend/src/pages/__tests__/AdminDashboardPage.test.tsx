import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/test-utils";
import AdminDashboardPage from "../AdminDashboardPage";
import * as api from "../../lib/api";

vi.mock("../../lib/api", () => ({
  fetchAdminOverviewV2: vi.fn(),
  fetchAdminFinanceV2: vi.fn(),
  fetchAdminUsageV2: vi.fn(),
  fetchAdminPendingPayoutsV2: vi.fn(),
  fetchAdminSecurityEventsV2: vi.fn(),
}));

describe("AdminDashboardPage", () => {
  const defaultProps = { token: "admin-token-123", creatorName: "Test Creator" };

  const mockOverview = {
    total_agents: 25,
    active_agents: 18,
    total_listings: 120,
    active_listings: 95,
    completed_transactions: 450,
    trust_weighted_revenue_usd: 12500.5,
  };

  const mockFinance = {
    platform_volume_usd: 50000.0,
    top_sellers_by_revenue: [
      { agent_id: "a1", agent_name: "Agent Alpha", money_received_usd: 5000 },
      { agent_id: "a2", agent_name: "Agent Beta", money_received_usd: 3000 },
      { agent_id: "a3", agent_name: "Agent Gamma", money_received_usd: 1500 },
    ],
  };

  const mockUsage = {
    info_used_count: 320,
    data_served_bytes: 4096000,
    money_saved_for_others_usd: 8750.25,
  };

  const mockPayouts = {
    count: 5,
    total_pending_usd: 1250.0,
    payouts: [],
  };

  const mockSecurity = {
    events: [
      {
        id: "ev-1",
        event_type: "login_attempt",
        severity: "warning",
        created_at: "2026-02-20T10:00:00Z",
      },
      {
        id: "ev-2",
        event_type: "rate_limit",
        severity: "info",
        created_at: "2026-02-20T09:00:00Z",
      },
      {
        id: "ev-3",
        event_type: "suspicious_transfer",
        severity: "critical",
        created_at: "2026-02-20T08:00:00Z",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchAdminOverviewV2).mockResolvedValue(mockOverview);
    vi.mocked(api.fetchAdminFinanceV2).mockResolvedValue(mockFinance);
    vi.mocked(api.fetchAdminUsageV2).mockResolvedValue(mockUsage);
    vi.mocked(api.fetchAdminPendingPayoutsV2).mockResolvedValue(mockPayouts);
    vi.mocked(api.fetchAdminSecurityEventsV2).mockResolvedValue(mockSecurity);
  });

  it("renders admin dashboard with title", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Admin Dashboard")).toBeInTheDocument();
    });
  });

  it("shows creator name in subtitle", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Platform operations and security controls - Test Creator/),
      ).toBeInTheDocument();
    });
  });

  it("shows system overview stats when data loads", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Platform Volume")).toBeInTheDocument();
    });
    expect(screen.getByText("$50.0K")).toBeInTheDocument();
    expect(screen.getByText("Completed Transactions")).toBeInTheDocument();
    expect(screen.getByText("450")).toBeInTheDocument();
    expect(screen.getByText("Pending Payouts")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows loading state while data is fetching", () => {
    vi.mocked(api.fetchAdminOverviewV2).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.fetchAdminFinanceV2).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.fetchAdminUsageV2).mockReturnValue(new Promise(() => {}));

    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    expect(screen.getByText("Loading admin dashboard...")).toBeInTheDocument();
  });

  it("shows error state when overview query fails", async () => {
    vi.mocked(api.fetchAdminOverviewV2).mockRejectedValue(
      new Error("Unauthorized"),
    );

    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText("Admin access required or token invalid."),
      ).toBeInTheDocument();
    });
  });

  it("shows agent stats section", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Agent Stats")).toBeInTheDocument();
    });
    expect(screen.getByText("Total agents: 25")).toBeInTheDocument();
    expect(screen.getByText("Active agents: 18")).toBeInTheDocument();
    expect(screen.getByText("Total listings: 120")).toBeInTheDocument();
    expect(screen.getByText("Active listings: 95")).toBeInTheDocument();
  });

  it("shows trust and savings section", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Trust + Savings")).toBeInTheDocument();
    });
    expect(screen.getByText(/Trust-weighted revenue:/)).toBeInTheDocument();
    expect(screen.getByText("Info used count: 320")).toBeInTheDocument();
    expect(screen.getByText(/Data served:/)).toBeInTheDocument();
    expect(screen.getByText(/Money saved for buyers:/)).toBeInTheDocument();
  });

  it("shows top sellers by revenue", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Top sellers by revenue")).toBeInTheDocument();
    });
    expect(screen.getByText("Agent Alpha")).toBeInTheDocument();
    expect(screen.getByText("Agent Beta")).toBeInTheDocument();
    expect(screen.getByText("Agent Gamma")).toBeInTheDocument();
  });

  it("shows security alerts count (non-info events)", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Security Alerts")).toBeInTheDocument();
    });
    // 2 non-info events (warning + critical)
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows recent security events", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Recent security events")).toBeInTheDocument();
    });
    expect(screen.getByText("login_attempt")).toBeInTheDocument();
    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("rate_limit")).toBeInTheDocument();
    expect(screen.getByText("suspicious_transfer")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("calls all API functions with the provided token", async () => {
    renderWithProviders(<AdminDashboardPage {...defaultProps} />);

    await waitFor(() => {
      expect(api.fetchAdminOverviewV2).toHaveBeenCalledWith("admin-token-123");
      expect(api.fetchAdminFinanceV2).toHaveBeenCalledWith("admin-token-123");
      expect(api.fetchAdminUsageV2).toHaveBeenCalledWith("admin-token-123");
      expect(api.fetchAdminPendingPayoutsV2).toHaveBeenCalledWith(
        "admin-token-123",
        20,
      );
      expect(api.fetchAdminSecurityEventsV2).toHaveBeenCalledWith(
        "admin-token-123",
        { page: 1, page_size: 15 },
      );
    });
  });
});
