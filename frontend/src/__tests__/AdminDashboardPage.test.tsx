import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AdminDashboardPage from "../pages/AdminDashboardPage";
import type {
  AdminOverviewV2,
  AdminFinanceV2,
  AdminUsageV2,
  AdminSecurityEventsV2,
} from "../types/api";

// ── Mock child components that are not under test ─────────────────────────────

vi.mock("../components/PageHeader", () => ({
  default: ({ title, subtitle }: { title: string; subtitle: string }) => (
    <div data-testid="page-header">
      <span>{title}</span>
      <span>{subtitle}</span>
    </div>
  ),
}));

// ── Mock API layer ─────────────────────────────────────────────────────────────

vi.mock("../lib/api", () => ({
  fetchAdminOverviewV2: vi.fn(),
  fetchAdminFinanceV2: vi.fn(),
  fetchAdminUsageV2: vi.fn(),
  fetchAdminPendingPayoutsV2: vi.fn(),
  fetchAdminSecurityEventsV2: vi.fn(),
}));

import {
  fetchAdminOverviewV2,
  fetchAdminFinanceV2,
  fetchAdminUsageV2,
  fetchAdminPendingPayoutsV2,
  fetchAdminSecurityEventsV2,
} from "../lib/api";

const mockOverview = vi.mocked(fetchAdminOverviewV2);
const mockFinance = vi.mocked(fetchAdminFinanceV2);
const mockUsage = vi.mocked(fetchAdminUsageV2);
const mockPayouts = vi.mocked(fetchAdminPendingPayoutsV2);
const mockSecurity = vi.mocked(fetchAdminSecurityEventsV2);

// ── Test fixtures ──────────────────────────────────────────────────────────────

const OVERVIEW: AdminOverviewV2 = {
  environment: "production",
  total_agents: 120,
  active_agents: 85,
  total_listings: 340,
  active_listings: 210,
  total_transactions: 5000,
  completed_transactions: 4800,
  platform_volume_usd: 75000,
  trust_weighted_revenue_usd: 62000,
  updated_at: "2024-01-01T00:00:00Z",
};

const FINANCE: AdminFinanceV2 = {
  platform_volume_usd: 75000,
  completed_transaction_count: 4800,
  payout_pending_count: 12,
  payout_pending_usd: 3200,
  payout_processing_count: 3,
  payout_processing_usd: 800,
  top_sellers_by_revenue: [
    { agent_id: "agent-1", agent_name: "Alpha Agent", money_received_usd: 12000 },
    { agent_id: "agent-2", agent_name: "Beta Agent", money_received_usd: 9500 },
    { agent_id: "agent-3", agent_name: "Gamma Agent", money_received_usd: 7200 },
  ],
  updated_at: "2024-01-01T00:00:00Z",
};

const USAGE: AdminUsageV2 = {
  info_used_count: 9800,
  data_served_bytes: 524288,
  unique_buyers_count: 310,
  unique_sellers_count: 95,
  money_saved_for_others_usd: 18000,
  category_breakdown: [],
  updated_at: "2024-01-01T00:00:00Z",
};

const PAYOUTS = {
  count: 12,
  total_pending_usd: 3200,
  requests: [],
};

const SECURITY_EVENTS: AdminSecurityEventsV2 = {
  total: 4,
  page: 1,
  page_size: 15,
  events: [
    {
      id: "ev-1",
      event_type: "failed_login",
      severity: "warning",
      agent_id: null,
      creator_id: null,
      ip_address: "192.168.1.1",
      details: {},
      created_at: "2024-01-01T10:00:00Z",
    },
    {
      id: "ev-2",
      event_type: "rate_limit_exceeded",
      severity: "error",
      agent_id: "agent-5",
      creator_id: null,
      ip_address: null,
      details: {},
      created_at: "2024-01-01T11:00:00Z",
    },
    {
      id: "ev-3",
      event_type: "healthcheck",
      severity: "info",
      agent_id: null,
      creator_id: null,
      ip_address: null,
      details: {},
      created_at: "2024-01-01T12:00:00Z",
    },
    {
      id: "ev-4",
      event_type: "suspicious_activity",
      severity: "critical",
      agent_id: "agent-6",
      creator_id: null,
      ip_address: "10.0.0.5",
      details: {},
      created_at: "2024-01-01T13:00:00Z",
    },
  ],
};

// ── Render helper ──────────────────────────────────────────────────────────────

function renderWithClient(
  token = "test-token",
  creatorName = "Admin User",
) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <AdminDashboardPage token={token} creatorName={creatorName} />
    </QueryClientProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("AdminDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: all queries remain pending (simulates loading state)
    mockOverview.mockReturnValue(new Promise(() => {}));
    mockFinance.mockReturnValue(new Promise(() => {}));
    mockUsage.mockReturnValue(new Promise(() => {}));
    mockPayouts.mockReturnValue(new Promise(() => {}));
    mockSecurity.mockReturnValue(new Promise(() => {}));
  });

  // ── 1. Error state ────────────────────────────────────────────────────────────

  it("renders error banner when overview query rejects", async () => {
    mockOverview.mockRejectedValue(new Error("API 403: Forbidden"));
    mockFinance.mockReturnValue(new Promise(() => {}));
    mockUsage.mockReturnValue(new Promise(() => {}));
    mockPayouts.mockReturnValue(new Promise(() => {}));
    mockSecurity.mockReturnValue(new Promise(() => {}));

    renderWithClient();

    await waitFor(() => {
      expect(
        screen.getByText("Admin access required or token invalid."),
      ).toBeInTheDocument();
    });
  });

  // ── 2. Loading state ──────────────────────────────────────────────────────────

  it("renders loading message while any of the three core queries is pending", () => {
    // All mocks remain as pending promises (set in beforeEach)
    renderWithClient();

    expect(screen.getByText("Loading admin dashboard...")).toBeInTheDocument();
  });

  it("renders loading message when overview resolves but finance is still pending", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockReturnValue(new Promise(() => {})); // still pending
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    // finance is pending so the loading state persists
    await waitFor(() => {
      expect(screen.getByText("Loading admin dashboard...")).toBeInTheDocument();
    });
  });

  // ── 3. Full dashboard rendered ────────────────────────────────────────────────

  it("renders the full dashboard with all stat cards when all queries resolve", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient("tok", "Alice Admin");

    await waitFor(() => {
      // Stat card labels
      expect(screen.getByText("Platform Volume")).toBeInTheDocument();
      expect(screen.getByText("Completed Transactions")).toBeInTheDocument();
      expect(screen.getByText("Pending Payouts")).toBeInTheDocument();
      expect(screen.getByText("Security Alerts")).toBeInTheDocument();
    });

    // Finance volume: 75000 → "$75.0K"
    expect(screen.getByText("$75.0K")).toBeInTheDocument();
    // Completed transactions
    expect(screen.getByText("4800")).toBeInTheDocument();
  });

  it("renders the page header with admin title and creator name", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient("tok", "Bob Admin");

    await waitFor(() => {
      expect(screen.getByText("Admin Dashboard")).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Platform operations and security controls - Bob Admin/),
    ).toBeInTheDocument();
  });

  // ── 4. totalAlerts filters out "info" severity ────────────────────────────────

  it("shows correct totalAlerts count by filtering out info-severity events", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);
    // SECURITY_EVENTS has 4 events: warning, error, info, critical → 3 non-info

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Security Alerts")).toBeInTheDocument();
    });

    // totalAlerts = 3 (excludes the "info" event)
    const alertsEl = screen.getByText("3");
    expect(alertsEl).toBeInTheDocument();
  });

  it("shows 0 totalAlerts when all security events have info severity", async () => {
    const allInfoEvents: AdminSecurityEventsV2 = {
      total: 2,
      page: 1,
      page_size: 15,
      events: [
        {
          id: "i1",
          event_type: "healthcheck",
          severity: "info",
          agent_id: null,
          creator_id: null,
          ip_address: null,
          details: {},
          created_at: "2024-01-01T10:00:00Z",
        },
        {
          id: "i2",
          event_type: "ping",
          severity: "info",
          agent_id: null,
          creator_id: null,
          ip_address: null,
          details: {},
          created_at: "2024-01-01T11:00:00Z",
        },
      ],
    };

    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(allInfoEvents);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Security Alerts")).toBeInTheDocument();
    });

    // All events are info → totalAlerts = 0
    // The "0" for security alerts is in the red cell
    const alertCells = screen.getAllByText("0");
    expect(alertCells.length).toBeGreaterThan(0);
  });

  it("shows 0 totalAlerts when security query has no data", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockReturnValue(new Promise(() => {})); // no data

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Security Alerts")).toBeInTheDocument();
    });

    // security.data is undefined → totalAlerts = 0
    const alertCells = screen.getAllByText("0");
    expect(alertCells.length).toBeGreaterThan(0);
  });

  // ── 5. Pending payouts count and amount ───────────────────────────────────────

  it("shows pending payouts count and formatted total amount", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue({ count: 12, total_pending_usd: 3200, requests: [] });
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Pending Payouts")).toBeInTheDocument();
    });

    // count = 12
    expect(screen.getByText("12")).toBeInTheDocument();
    // total_pending_usd = 3200 → "$3.2K"
    expect(screen.getByText("$3.2K")).toBeInTheDocument();
  });

  it("shows 0 count and $0.00 when payouts query has no data", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockReturnValue(new Promise(() => {})); // no data
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Pending Payouts")).toBeInTheDocument();
    });

    // payouts.data is undefined → count = 0, total = 0
    expect(screen.getByText("$0.00")).toBeInTheDocument();
  });

  // ── 6. Top sellers by revenue ─────────────────────────────────────────────────

  it("renders top sellers list from finance data", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Top sellers by revenue")).toBeInTheDocument();
    });

    expect(screen.getByText("Alpha Agent")).toBeInTheDocument();
    expect(screen.getByText("Beta Agent")).toBeInTheDocument();
    expect(screen.getByText("Gamma Agent")).toBeInTheDocument();
    // Alpha Agent: $12000 → "$12.0K"
    expect(screen.getByText("$12.0K")).toBeInTheDocument();
    // Beta Agent: $9500 → "$9.5K"
    expect(screen.getByText("$9.5K")).toBeInTheDocument();
  });

  it("renders at most 8 top sellers when more than 8 are returned", async () => {
    const manySellerFinance: AdminFinanceV2 = {
      ...FINANCE,
      top_sellers_by_revenue: Array.from({ length: 10 }, (_, i) => ({
        agent_id: `agent-${i}`,
        agent_name: `Seller ${i + 1}`,
        money_received_usd: 1000 * (10 - i),
      })),
    };

    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(manySellerFinance);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Top sellers by revenue")).toBeInTheDocument();
    });

    // slice(0, 8) → only first 8 should appear
    expect(screen.getByText("Seller 1")).toBeInTheDocument();
    expect(screen.getByText("Seller 8")).toBeInTheDocument();
    expect(screen.queryByText("Seller 9")).not.toBeInTheDocument();
    expect(screen.queryByText("Seller 10")).not.toBeInTheDocument();
  });

  // ── 7. Security events list ───────────────────────────────────────────────────

  it("renders security events list with event type and severity", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Recent security events")).toBeInTheDocument();
    });

    expect(screen.getByText("failed_login")).toBeInTheDocument();
    expect(screen.getByText("rate_limit_exceeded")).toBeInTheDocument();
    expect(screen.getByText("healthcheck")).toBeInTheDocument();
    expect(screen.getByText("suspicious_activity")).toBeInTheDocument();

    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("error")).toBeInTheDocument();
    expect(screen.getByText("info")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("renders empty security events section when security query has no data", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockReturnValue(new Promise(() => {})); // no data

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Recent security events")).toBeInTheDocument();
    });

    // With no security data the events list renders nothing
    expect(screen.queryByText("failed_login")).not.toBeInTheDocument();
  });

  // ── 8. Agent stats card ───────────────────────────────────────────────────────

  it("renders agent stats from overview data", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Agent Stats")).toBeInTheDocument();
    });

    expect(screen.getByText(/Total agents: 120/)).toBeInTheDocument();
    expect(screen.getByText(/Active agents: 85/)).toBeInTheDocument();
    expect(screen.getByText(/Total listings: 340/)).toBeInTheDocument();
    expect(screen.getByText(/Active listings: 210/)).toBeInTheDocument();
  });

  // ── 9. Trust + Savings card ───────────────────────────────────────────────────

  it("renders trust and savings data from overview and usage", async () => {
    mockOverview.mockResolvedValue(OVERVIEW);
    mockFinance.mockResolvedValue(FINANCE);
    mockUsage.mockResolvedValue(USAGE);
    mockPayouts.mockResolvedValue(PAYOUTS);
    mockSecurity.mockResolvedValue(SECURITY_EVENTS);

    renderWithClient();

    await waitFor(() => {
      expect(screen.getByText("Trust + Savings")).toBeInTheDocument();
    });

    // trust_weighted_revenue_usd: 62000 → "$62.0K" rendered inline in the div text
    expect(screen.getByText(/Trust-weighted revenue:.*\$62\.0K/)).toBeInTheDocument();
    // info_used_count: 9800
    expect(screen.getByText(/Info used count: 9800/)).toBeInTheDocument();
    // data_served_bytes: 524288
    expect(screen.getByText(/524,288 bytes/)).toBeInTheDocument();
    // money_saved_for_others_usd: 18000 → "$18.0K"
    expect(screen.getByText(/Money saved for buyers:.*\$18\.0K/)).toBeInTheDocument();
  });
});
