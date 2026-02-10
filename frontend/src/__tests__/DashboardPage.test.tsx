/// <reference types="vitest/globals" />
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardPage } from "../pages/DashboardPage";
import type { Loan, DashboardSummary, LoanInsight } from "../types";

// ── Mock api module ──────────────────────────────────────────────────────────
vi.mock("../lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import api from "../lib/api";
const mockGet = vi.mocked(api.get);
const mockPost = vi.mocked(api.post);

// ── Mock useNavigate ─────────────────────────────────────────────────────────
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// ── Mock AnimatedNumber (uses requestAnimationFrame which doesn't work in JSDOM) ──
vi.mock("../components/shared/AnimatedNumber", () => ({
  AnimatedNumber: ({ value, formatter, className }: { value: number; formatter?: (n: number) => string; className?: string }) => (
    <span className={className}>{formatter ? formatter(Math.round(value)) : Math.round(value).toLocaleString()}</span>
  ),
}));

// ── Mock useCountryConfig (used by CurrencyDisplay) ──────────────────────────
vi.mock("../hooks/useCountryConfig", () => ({
  useCountryConfig: () => ({
    code: "IN",
    currencyCode: "INR",
    currencySymbol: "\u20B9",
    currencyLocale: "en-IN",
  }),
}));

// ── Test data ────────────────────────────────────────────────────────────────
const makeLoan = (overrides: Partial<Loan> = {}): Loan => ({
  id: "loan-1",
  user_id: "user-1",
  bank_name: "HDFC",
  loan_type: "home",
  principal_amount: 5000000,
  outstanding_principal: 4000000,
  interest_rate: 8.5,
  interest_rate_type: "floating",
  tenure_months: 240,
  remaining_tenure_months: 200,
  emi_amount: 43391,
  emi_due_date: 5,
  prepayment_penalty_pct: 0,
  foreclosure_charges_pct: 0,
  eligible_80c: false,
  eligible_24b: true,
  eligible_80e: false,
  eligible_80eea: false,
  disbursement_date: "2023-01-15",
  status: "active",
  source: "manual",
  source_scan_id: null,
  created_at: "2023-01-15T00:00:00Z",
  updated_at: "2023-01-15T00:00:00Z",
  ...overrides,
});

const LOAN_A = makeLoan({
  id: "loan-1",
  bank_name: "HDFC",
  loan_type: "home",
  outstanding_principal: 4000000,
  emi_amount: 43391,
  interest_rate: 8.5,
  remaining_tenure_months: 200,
  principal_amount: 5000000,
});

const LOAN_B = makeLoan({
  id: "loan-2",
  bank_name: "ICICI",
  loan_type: "personal",
  outstanding_principal: 500000,
  emi_amount: 18000,
  interest_rate: 14.5,
  remaining_tenure_months: 36,
  principal_amount: 600000,
});

const CLOSED_LOAN = makeLoan({
  id: "loan-3",
  bank_name: "SBI",
  loan_type: "car",
  status: "closed",
});

const MOCK_SUMMARY: DashboardSummary = {
  has_loans: true,
  loan_count: 2,
  total_debt: 4500000,
  total_emi: 61391,
  suggested_extra: 5000,
  recommended_strategy: "avalanche",
  interest_saved: 250000,
  months_saved: 18,
  debt_free_months: 182,
  baseline_months: 200,
  strategies_preview: [
    { name: "avalanche", interest_saved: 250000, months_saved: 18 },
    { name: "snowball", interest_saved: 200000, months_saved: 15 },
    { name: "hybrid", interest_saved: 230000, months_saved: 17 },
  ],
};

const MOCK_INSIGHTS: LoanInsight[] = [
  { loan_id: "loan-1", text: "Your home loan rate is competitive. Consider making occasional lump-sum prepayments to reduce interest burden over the long tenure." },
  { loan_id: "loan-2", text: "High interest rate. Prioritize paying off this loan first." },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
    },
  });
}

function renderDashboard() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

/**
 * Configure api mocks so that /api/loans resolves with the given loans array,
 * /api/optimizer/dashboard-summary resolves with summary, and
 * /api/ai/explain-loans-batch resolves with insights.
 */
function setupApiMocks(
  loans: Loan[] = [],
  summary: DashboardSummary | null = null,
  insights: LoanInsight[] = [],
) {
  mockGet.mockImplementation((url: string) => {
    if (url === "/api/loans") {
      return Promise.resolve({ data: loans }) as any;
    }
    if (url === "/api/optimizer/dashboard-summary") {
      return Promise.resolve({ data: summary ?? MOCK_SUMMARY }) as any;
    }
    return Promise.reject(new Error(`Unhandled GET ${url}`)) as any;
  });

  mockPost.mockImplementation((url: string) => {
    if (url === "/api/ai/explain-loans-batch") {
      return Promise.resolve({ data: { insights } }) as any;
    }
    return Promise.reject(new Error(`Unhandled POST ${url}`)) as any;
  });
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── 1. Loading spinner ─────────────────────────────────────────────────────
  describe("Loading state", () => {
    it("shows skeleton loading state initially while loans are being fetched", () => {
      // Never resolve the loans request so we stay in loading state
      mockGet.mockImplementation(
        () => new Promise(() => {}) as any,
      );

      renderDashboard();

      // DashboardSkeleton renders shimmer skeleton elements
      const skeleton = document.querySelector(".skeleton");
      expect(skeleton).toBeInTheDocument();
    });
  });

  // ── 2. Empty state ─────────────────────────────────────────────────────────
  describe("Empty state", () => {
    it("shows empty state when no active loans exist", async () => {
      setupApiMocks([]);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.noLoansYet")).toBeInTheDocument();
      });
      expect(screen.getByText("dashboard.noLoansDesc")).toBeInTheDocument();
      expect(screen.getByText("dashboard.addLoan")).toBeInTheDocument();
    });

    it("shows empty state when all loans are closed", async () => {
      setupApiMocks([CLOSED_LOAN]);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.noLoansYet")).toBeInTheDocument();
      });
    });

    it("navigates to scanner when empty state add-loan button is clicked", async () => {
      setupApiMocks([]);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.addLoan")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("dashboard.addLoan"));
      expect(mockNavigate).toHaveBeenCalledWith("/scanner");
    });
  });

  // ── 3. Loan cards rendering ────────────────────────────────────────────────
  describe("Loan cards", () => {
    it("renders loan cards for each active loan", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });
      expect(screen.getByText("ICICI")).toBeInTheDocument();
    });

    it("displays loan type badge on each card", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("home")).toBeInTheDocument();
      });
      expect(screen.getByText("personal")).toBeInTheDocument();
    });

    it("shows interest rate on each card", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("8.5%")).toBeInTheDocument();
      });
      expect(screen.getByText("14.5%")).toBeInTheDocument();
    });

    it("shows repayment progress percentage", async () => {
      // LOAN_A: outstanding=4000000, principal=5000000 => 20% paid
      setupApiMocks([LOAN_A], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("20% dashboard.paid")).toBeInTheDocument();
      });
    });

    it("does not render closed loans", async () => {
      setupApiMocks([LOAN_A, CLOSED_LOAN], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });
      expect(screen.queryByText("SBI")).not.toBeInTheDocument();
    });
  });

  // ── 4. Total debt and EMI summary ──────────────────────────────────────────
  describe("Summary cards", () => {
    it("shows total debt summary card with computed value", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.totalDebt")).toBeInTheDocument();
      });
      // total_debt = 4,000,000 + 500,000 = 4,500,000 → formatINR → "₹45,00,000"
      expect(screen.getByText("₹45,00,000")).toBeInTheDocument();
    });

    it("shows monthly EMI summary card with computed value", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.monthlyEmi")).toBeInTheDocument();
      });
      expect(screen.getByText("dashboard.perMonth")).toBeInTheDocument();
      // total_emi = 43,391 + 18,000 = 61,391 → formatINR → "₹61,391"
      expect(screen.getByText("₹61,391")).toBeInTheDocument();
    });

    it("shows debt-free-by summary card", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.debtFreeBy")).toBeInTheDocument();
      });
    });

    it("shows active loan count", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        // t("dashboard.activeLoans", { count: 2 }) -> "dashboard.activeLoans"
        // The mock t function will replace {{count}} with 2
        expect(screen.getByText(/dashboard\.activeLoans/)).toBeInTheDocument();
      });
    });

    it("shows portfolio health section with average rate", async () => {
      // avgRate = (8.5 + 14.5) / 2 = 11.5
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.portfolioHealth")).toBeInTheDocument();
      });
      expect(screen.getByText("11.5%")).toBeInTheDocument();
    });

    it("shows highest risk loan in portfolio health", async () => {
      // LOAN_B has the highest rate at 14.5%
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("ICICI (14.5%)")).toBeInTheDocument();
      });
    });
  });

  // ── 5. Quick compare / strategies preview ──────────────────────────────────
  describe("Strategy preview (savings)", () => {
    it("shows optimizer savings banner when interest can be saved", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.aiRecommendation")).toBeInTheDocument();
      });
      // "youCouldSave", CurrencyDisplay, and "inInterest" are siblings inside a <p>,
      // so we need to use a function matcher or regex to find the combined text.
      expect(screen.getByText(/dashboard\.youCouldSave/)).toBeInTheDocument();
      expect(screen.getByText(/dashboard\.inInterest/)).toBeInTheDocument();
    });

    it("shows strategy preview cards", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.strategyPreview")).toBeInTheDocument();
      });
      // Strategy names are displayed with capitalize and _ replaced by space
      expect(screen.getByText("avalanche")).toBeInTheDocument();
      expect(screen.getByText("snowball")).toBeInTheDocument();
      expect(screen.getByText("hybrid")).toBeInTheDocument();
    });

    it("marks the recommended strategy", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("optimizer.strategy.recommended")).toBeInTheDocument();
      });
    });

    it("does not show savings banner when interest_saved is 0", async () => {
      const noSavings: DashboardSummary = { ...MOCK_SUMMARY, interest_saved: 0 };
      setupApiMocks([LOAN_A, LOAN_B], noSavings, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });
      expect(screen.queryByText("dashboard.aiRecommendation")).not.toBeInTheDocument();
    });

    it("navigates to optimizer when view-strategies button is clicked", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("dashboard.viewStrategies")).toBeInTheDocument();
      });

      // There may be multiple "viewStrategies" buttons (banner + quick actions)
      const buttons = screen.getAllByText("dashboard.viewStrategies");
      fireEvent.click(buttons[0]);
      expect(mockNavigate).toHaveBeenCalledWith("/optimizer");
    });
  });

  // ── 6. API error handling ──────────────────────────────────────────────────
  describe("API error handling", () => {
    it("handles loan fetch error gracefully and shows empty state", async () => {
      mockGet.mockImplementation((url: string) => {
        if (url === "/api/loans") {
          return Promise.reject(new Error("Network error")) as any;
        }
        return Promise.resolve({ data: null }) as any;
      });

      renderDashboard();

      // After error, the component should eventually resolve
      // react-query will set data to undefined, which means activeLoans = []
      // so the empty state should appear
      await waitFor(() => {
        expect(screen.getByText("dashboard.noLoansYet")).toBeInTheDocument();
      });
    });

    it("renders loans even if summary endpoint fails", async () => {
      mockGet.mockImplementation((url: string) => {
        if (url === "/api/loans") {
          return Promise.resolve({ data: [LOAN_A] }) as any;
        }
        if (url === "/api/optimizer/dashboard-summary") {
          return Promise.reject(new Error("Summary error")) as any;
        }
        return Promise.reject(new Error(`Unhandled GET ${url}`)) as any;
      });
      mockPost.mockRejectedValue(new Error("Insights error") as any);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });
      // Summary-dependent elements should not crash the page
      expect(screen.getByText("dashboard.totalDebt")).toBeInTheDocument();
    });

    it("renders loans even if insights endpoint fails", async () => {
      mockGet.mockImplementation((url: string) => {
        if (url === "/api/loans") {
          return Promise.resolve({ data: [LOAN_A] }) as any;
        }
        if (url === "/api/optimizer/dashboard-summary") {
          return Promise.resolve({ data: MOCK_SUMMARY }) as any;
        }
        return Promise.reject(new Error(`Unhandled GET ${url}`)) as any;
      });
      mockPost.mockRejectedValue(new Error("AI service unavailable") as any);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });
      // Page still renders without AI insights
      expect(screen.getByText("dashboard.totalDebt")).toBeInTheDocument();
    });
  });

  // ── 7. AI insights on loan cards ───────────────────────────────────────────
  describe("AI insights", () => {
    it("shows AI insight text on loan cards when available", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, MOCK_INSIGHTS);

      renderDashboard();

      await waitFor(() => {
        // LOAN_B insight is short (<100 chars), shown in full
        expect(
          screen.getByText("High interest rate. Prioritize paying off this loan first.")
        ).toBeInTheDocument();
      });
    });

    it("truncates long insight text with ellipsis", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, MOCK_INSIGHTS);

      renderDashboard();

      await waitFor(() => {
        // LOAN_A insight is >100 chars, should be truncated
        const truncated = MOCK_INSIGHTS[0].text.slice(0, 100) + "...";
        expect(screen.getByText(truncated)).toBeInTheDocument();
      });
    });

    it("expands truncated insight text on click", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, MOCK_INSIGHTS);

      renderDashboard();

      await waitFor(() => {
        const truncated = MOCK_INSIGHTS[0].text.slice(0, 100) + "...";
        expect(screen.getByText(truncated)).toBeInTheDocument();
      });

      // Click the insight area to expand it
      const truncated = MOCK_INSIGHTS[0].text.slice(0, 100) + "...";
      const insightElement = screen.getByText(truncated);
      // Click the parent container (the border-t div)
      const insightContainer = insightElement.closest(".border-t")!;
      fireEvent.click(insightContainer);

      // Full text should now be visible
      await waitFor(() => {
        expect(screen.getByText(MOCK_INSIGHTS[0].text)).toBeInTheDocument();
      });
    });

    it("does not show insight section when no insights available", async () => {
      setupApiMocks([LOAN_A], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });

      // No border-t insight containers should exist
      const insightContainers = document.querySelectorAll(".border-t.border-gray-100.px-4");
      expect(insightContainers.length).toBe(0);
    });
  });

  // ── 8. Navigate to loan detail on card click ───────────────────────────────
  describe("Navigation", () => {
    it("navigates to loan detail page when a loan card is clicked", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });

      // Click on HDFC loan card (the clickable area with cursor-pointer)
      const hdfcText = screen.getByText("HDFC");
      const clickableArea = hdfcText.closest(".cursor-pointer")!;
      fireEvent.click(clickableArea);

      expect(mockNavigate).toHaveBeenCalledWith("/loans/loan-1");
    });

    it("navigates to correct loan detail for second loan card", async () => {
      setupApiMocks([LOAN_A, LOAN_B], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("ICICI")).toBeInTheDocument();
      });

      const iciciText = screen.getByText("ICICI");
      const clickableArea = iciciText.closest(".cursor-pointer")!;
      fireEvent.click(clickableArea);

      expect(mockNavigate).toHaveBeenCalledWith("/loans/loan-2");
    });

    it("navigates to scanner when add-loan quick action is clicked", async () => {
      setupApiMocks([LOAN_A], MOCK_SUMMARY, []);

      renderDashboard();

      await waitFor(() => {
        expect(screen.getByText("HDFC")).toBeInTheDocument();
      });

      // The quick action "Add Loan" button in the button bar
      const addButtons = screen.getAllByText("dashboard.addLoan");
      fireEvent.click(addButtons[0]);
      expect(mockNavigate).toHaveBeenCalledWith("/scanner");
    });
  });
});
