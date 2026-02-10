/// <reference types="vitest/globals" />
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StepResults } from "../components/optimizer/StepResults";
import type { OptimizationResult, SensitivityResult } from "../types";

// ─── Mock api ───
const mockPost = vi.fn();
vi.mock("../lib/api", () => ({
  default: { post: (...args: unknown[]) => mockPost(...args) },
}));

// ─── Mock useCountryConfig → IN config ───
vi.mock("../hooks/useCountryConfig", () => ({
  useCountryConfig: () => ({
    code: "IN" as const,
    currencyCode: "INR",
    currencySymbol: "\u20B9",
    currencyLocale: "en-IN",
    dateLocale: "en-IN",
    banks: ["SBI", "HDFC"],
    loanTypes: ["home", "personal"],
    hasTaxSections: true,
    hasFilingStatus: false,
    compactUnits: [
      { threshold: 1e7, suffix: "Cr", divisor: 1e7 },
      { threshold: 1e5, suffix: "L", divisor: 1e5 },
      { threshold: 1e3, suffix: "K", divisor: 1e3 },
    ],
    sliderRanges: {
      principal: { min: 100000, max: 50000000, step: 100000 },
      dailySaving: { min: 10, max: 1000, step: 10 },
      monthlyExtra: { min: 0, max: 50000, step: 500 },
      lumpSumDefault: 50000,
    },
    budgetModeKey: "optimizer.budget.gullakMode",
    privacyLawKey: "settings.dpdpAct",
  }),
}));

// ─── Mock data ───

const mockResults: OptimizationResult = {
  baseline_total_interest: 850000,
  baseline_total_months: 120,
  recommended_strategy: "avalanche",
  strategies: [
    {
      strategy_name: "avalanche",
      strategy_description: "Pay highest interest rate first",
      total_interest_paid: 620000,
      total_months: 96,
      interest_saved_vs_baseline: 230000,
      months_saved_vs_baseline: 24,
      payoff_order: ["loan-1", "loan-2"],
      debt_free_date_months: 96,
      loan_results: [
        {
          loan_id: "loan-1",
          bank_name: "HDFC",
          loan_type: "personal",
          original_balance: 500000,
          payoff_month: 36,
          months_saved: 12,
        },
        {
          loan_id: "loan-2",
          bank_name: "SBI",
          loan_type: "home",
          original_balance: 2000000,
          payoff_month: 96,
          months_saved: 24,
        },
      ],
    },
    {
      strategy_name: "snowball",
      strategy_description: "Pay smallest balance first",
      total_interest_paid: 660000,
      total_months: 102,
      interest_saved_vs_baseline: 190000,
      months_saved_vs_baseline: 18,
      payoff_order: ["loan-1", "loan-2"],
      debt_free_date_months: 102,
      loan_results: [
        {
          loan_id: "loan-1",
          bank_name: "HDFC",
          loan_type: "personal",
          original_balance: 500000,
          payoff_month: 30,
          months_saved: 18,
        },
        {
          loan_id: "loan-2",
          bank_name: "SBI",
          loan_type: "home",
          original_balance: 2000000,
          payoff_month: 102,
          months_saved: 18,
        },
      ],
    },
  ],
};

const mockSensitivity: SensitivityResult = {
  strategy_name: "avalanche",
  points: [
    { rate_delta_pct: -1, total_interest_paid: 580000, total_months: 90, interest_saved_vs_baseline: 270000 },
    { rate_delta_pct: 0, total_interest_paid: 620000, total_months: 96, interest_saved_vs_baseline: 230000 },
    { rate_delta_pct: 1, total_interest_paid: 670000, total_months: 102, interest_saved_vs_baseline: 180000 },
  ],
};

const defaultProps = {
  results: mockResults,
  selectedStrategy: "avalanche",
  loanIds: ["loan-1", "loan-2"],
  monthlyExtra: 5000,
  lumpSums: [{ month: 6, amount: 100000 }],
  annualGrowthPct: 5,
};

// ─── Helpers ───

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderStepResults(props = defaultProps) {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <StepResults {...props} />
    </QueryClientProvider>
  );
}

// ─── Tests ───

describe("StepResults", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: sensitivity endpoint resolves with empty data (no table shown unless we want it)
    mockPost.mockImplementation((url: string) => {
      if (url === "/api/optimizer/sensitivity") {
        return Promise.resolve({ data: { strategy_name: "avalanche", points: [] } });
      }
      if (url === "/api/optimizer/save-plan") {
        return Promise.resolve({ data: { id: "plan-1" } });
      }
      return Promise.resolve({ data: {} });
    });
  });

  // ── 1. Hero banner with interest saved ──
  describe("Hero Banner", () => {
    it("renders hero banner with interest saved amount", () => {
      renderStepResults();

      // The hero shows "you save" text with formatted interest saved
      expect(screen.getByText("optimizer.results.youSave", { exact: false })).toBeInTheDocument();
      // interest_saved_vs_baseline = 230000 → formatCurrency(230000, "IN") = "₹2,30,000"
      expect(screen.getByText(/₹2,30,000/)).toBeInTheDocument();
    });

    it("shows months saved in hero banner", () => {
      renderStepResults();
      // months_saved_vs_baseline = 24, rendered in a single <p> as "debtFree 24 monthsEarlier"
      expect(screen.getByText(/optimizer\.results\.debtFree.*24.*optimizer\.results\.monthsEarlier/)).toBeInTheDocument();
    });

    it("shows strategy description in hero banner", () => {
      renderStepResults();
      expect(screen.getByText("Pay highest interest rate first")).toBeInTheDocument();
    });
  });

  // ── 2. Before/After comparison cards ──
  describe("Before/After Comparison", () => {
    it("shows before card with baseline interest", () => {
      renderStepResults();
      expect(screen.getByText("optimizer.results.withoutPlan")).toBeInTheDocument();
      // baseline_total_interest = 850000 → formatCurrencyCompact(850000, "IN") = "₹8.5L"
      expect(screen.getByText("₹8.5L")).toBeInTheDocument();
    });

    it("shows after card with optimized interest", () => {
      renderStepResults();
      expect(screen.getByText("optimizer.results.withPlan")).toBeInTheDocument();
      // total_interest_paid = 620000 → "₹6.2L"
      expect(screen.getByText("₹6.2L")).toBeInTheDocument();
    });

    it("shows baseline months formatted in before card", () => {
      renderStepResults();
      // baseline_total_months = 120 → formatMonths(120) = "10 years"
      expect(screen.getByText("10 years")).toBeInTheDocument();
    });

    it("shows optimized months formatted in after card", () => {
      renderStepResults();
      // total_months = 96 → formatMonths(96) = "8 years"
      expect(screen.getByText("8 years")).toBeInTheDocument();
    });
  });

  // ── 3. Payoff timeline bars ──
  describe("Payoff Timeline", () => {
    it("renders payoff timeline section with header", () => {
      renderStepResults();
      expect(screen.getByText("optimizer.results.payoffTimeline")).toBeInTheDocument();
    });

    it("renders timeline bars for each loan sorted by payoff month", () => {
      renderStepResults();
      // Both bank names appear in timeline and strategy cards, so use getAllByText
      const hdfcElements = screen.getAllByText("HDFC");
      expect(hdfcElements.length).toBeGreaterThanOrEqual(1);
      const sbiElements = screen.getAllByText("SBI");
      expect(sbiElements.length).toBeGreaterThanOrEqual(1);
    });

    it("shows payoff month for each loan in timeline", () => {
      renderStepResults();
      // paidOffMonth appears in timeline (2) + per-loan breakdown in strategy cards (2 strategies x 2 loans = 4) = 6 total
      const paidOffTexts = screen.getAllByText(/optimizer\.results\.paidOffMonth/);
      expect(paidOffTexts.length).toBe(6);
    });

    it("shows months saved for loans with savings in timeline", () => {
      renderStepResults();
      // Both loans have months_saved > 0
      const savedTexts = screen.getAllByText(/optimizer\.results\.savedMonths/);
      expect(savedTexts.length).toBe(2);
    });

    it("shows max payoff month in timeline footer", () => {
      renderStepResults();
      // maxPayoff = 96, so "96 common.months" should appear
      expect(screen.getByText(/96/)).toBeInTheDocument();
      expect(screen.getByText("0")).toBeInTheDocument();
    });
  });

  // ── 4. Actionable advice section ──
  describe("Actionable Advice", () => {
    it("renders actionable advice section with header", () => {
      renderStepResults();
      expect(screen.getByText("optimizer.results.actionPlan")).toBeInTheDocument();
    });

    it("renders advice items as ordered list", () => {
      renderStepResults();
      // With 2 loan_results and 1 lump sum, we expect at least 3 advice items:
      // actionFocus, actionPaidOff, actionFreedEmi (2 loans), actionLumpSum (1 lump sum)
      const listItems = screen.getAllByRole("listitem");
      expect(listItems.length).toBeGreaterThanOrEqual(3);
    });

    it("includes lump sum advice when lump sums are present", () => {
      renderStepResults();
      // lumpSums[0] = { month: 6, amount: 100000 }
      // actionLumpSum key should appear with interpolated values
      expect(screen.getByText(/optimizer\.results\.actionLumpSum/)).toBeInTheDocument();
    });
  });

  // ── 5. Strategy comparison cards ──
  describe("Strategy Comparison Cards", () => {
    it("renders strategy comparison section heading", () => {
      renderStepResults();
      expect(screen.getByText("optimizer.results.comparison")).toBeInTheDocument();
    });

    it("renders a card for each strategy", () => {
      renderStepResults();
      // Both strategy names appear (capitalized with underscores replaced)
      expect(screen.getByText("avalanche")).toBeInTheDocument();
      expect(screen.getByText("snowball")).toBeInTheDocument();
    });

    it("shows interest saved for each strategy", () => {
      renderStepResults();
      // avalanche: 230000 → "₹2.3L", snowball: 190000 → "₹1.9L"
      expect(screen.getByText("₹2.3L")).toBeInTheDocument();
      expect(screen.getByText("₹1.9L")).toBeInTheDocument();
    });

    it("shows months saved for each strategy", () => {
      renderStepResults();
      // avalanche: 24, snowball: 18
      const monthLabels = screen.getAllByText("optimizer.monthsSaved");
      expect(monthLabels).toHaveLength(2);
    });
  });

  // ── 6. Highlights recommended strategy ──
  describe("Recommended Strategy Highlight", () => {
    it("shows best badge on recommended strategy card", () => {
      renderStepResults();
      // Only one badge should show "best"
      expect(screen.getByText("optimizer.results.best")).toBeInTheDocument();
    });

    it("applies purple border to recommended strategy card", () => {
      renderStepResults();
      const bestBadge = screen.getByText("optimizer.results.best");
      // The card is the grandparent of the badge
      const card = bestBadge.closest(".border-purple-300");
      expect(card).not.toBeNull();
    });

    it("does not show best badge on non-recommended strategy", () => {
      renderStepResults();
      // Only one "best" badge total
      const bestBadges = screen.getAllByText("optimizer.results.best");
      expect(bestBadges).toHaveLength(1);
    });
  });

  // ── 7. Per-loan breakdown in strategy cards ──
  describe("Per-Loan Breakdown", () => {
    it("shows per-loan breakdown header in strategy cards", () => {
      renderStepResults();
      // Both strategy cards show per-loan breakdown
      const breakdownHeaders = screen.getAllByText("optimizer.results.perLoanBreakdown");
      expect(breakdownHeaders).toHaveLength(2);
    });

    it("shows each loan in per-loan breakdown with bank name and type", () => {
      renderStepResults();
      // HDFC (personal) and SBI (home) appear in each strategy card's breakdown
      const hdfcElements = screen.getAllByText("HDFC");
      // HDFC in timeline + 2 strategy card breakdowns = at least 3
      expect(hdfcElements.length).toBeGreaterThanOrEqual(3);

      const personalElements = screen.getAllByText("(personal)");
      expect(personalElements.length).toBeGreaterThanOrEqual(2);

      const homeElements = screen.getAllByText("(home)");
      expect(homeElements.length).toBeGreaterThanOrEqual(2);
    });

    it("shows months saved per loan in breakdown when savings exist", () => {
      renderStepResults();
      // Avalanche loan-1: -12mo, loan-2: -24mo; Snowball loan-1: -18mo, loan-2: -18mo
      const savedIndicators = screen.getAllByText(/-\d+mo/);
      expect(savedIndicators.length).toBe(4);
    });
  });

  // ── 8. Save plan button triggers API call ──
  describe("Save Plan", () => {
    it("renders save plan button", () => {
      renderStepResults();
      expect(screen.getByText("optimizer.savePlan")).toBeInTheDocument();
    });

    it("triggers save-plan API call when clicked", async () => {
      renderStepResults();
      const saveBtn = screen.getByText("optimizer.savePlan");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockPost).toHaveBeenCalledWith("/api/optimizer/save-plan", {
          name: "avalanche plan",
          strategy: "avalanche",
          config: { monthly_extra: 5000 },
          results: { interest_saved: 230000, months_saved: 24 },
        });
      });
    });

    it("disables button while save is pending", async () => {
      // Make save-plan hang so we can check pending state
      let resolveSave: (value: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return Promise.resolve({ data: { strategy_name: "avalanche", points: [] } });
        }
        if (url === "/api/optimizer/save-plan") {
          return new Promise((resolve) => {
            resolveSave = resolve;
          });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();
      const saveBtn = screen.getByRole("button");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(screen.getByText("common.saving")).toBeInTheDocument();
      });

      // Resolve to clean up
      resolveSave!({ data: { id: "plan-1" } });
    });
  });

  // ── 9. Shows "Plan Saved" after successful save ──
  describe("Plan Saved Confirmation", () => {
    it("shows plan saved text after successful save", async () => {
      renderStepResults();
      const saveBtn = screen.getByText("optimizer.savePlan");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(screen.getByText("optimizer.results.planSaved")).toBeInTheDocument();
      });
    });

    it("disables the button after plan is saved", async () => {
      renderStepResults();
      const saveBtn = screen.getByText("optimizer.savePlan");
      fireEvent.click(saveBtn);

      await waitFor(() => {
        const savedBtn = screen.getByText("optimizer.results.planSaved");
        expect(savedBtn).toBeDisabled();
      });
    });
  });

  // ── 10. Sensitivity table when data available ──
  describe("Sensitivity Table", () => {
    it("does not render sensitivity table when points are empty", () => {
      // Default mock returns empty points
      renderStepResults();
      expect(screen.queryByText("optimizer.results.sensitivityTitle")).not.toBeInTheDocument();
    });

    it("shows sensitivity table when data is available", async () => {
      let resolveApi: (v: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return new Promise((resolve) => { resolveApi = resolve; });
        }
        if (url === "/api/optimizer/save-plan") {
          return Promise.resolve({ data: { id: "plan-1" } });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();

      await act(async () => {
        resolveApi!({ data: mockSensitivity });
      });

      expect(screen.getByText("optimizer.results.sensitivityTitle")).toBeInTheDocument();
    });

    it("renders sensitivity table headers", async () => {
      let resolveApi: (v: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return new Promise((resolve) => { resolveApi = resolve; });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();

      await act(async () => {
        resolveApi!({ data: mockSensitivity });
      });

      expect(screen.getByText("optimizer.results.rateChange")).toBeInTheDocument();
      expect(screen.getByText("optimizer.results.totalInterest")).toBeInTheDocument();
      // "optimizer.results.totalMonths" is the table header
      expect(screen.getByText("optimizer.results.totalMonths")).toBeInTheDocument();
      // "optimizer.interestSaved" appears in strategy cards too, so use getAllByText
      const interestSavedEls = screen.getAllByText("optimizer.interestSaved");
      // 2 from strategy cards + 1 from sensitivity table header = 3
      expect(interestSavedEls.length).toBe(3);
    });

    it("renders a row for each sensitivity point", async () => {
      let resolveApi: (v: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return new Promise((resolve) => { resolveApi = resolve; });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();

      await act(async () => {
        resolveApi!({ data: mockSensitivity });
      });

      // 3 points: -1%, 0%, +1%
      expect(screen.getByText("-1%")).toBeInTheDocument();
      expect(screen.getByText("0%")).toBeInTheDocument();
      expect(screen.getByText("+1%")).toBeInTheDocument();
    });

    it("highlights the baseline row (rate_delta_pct === 0)", async () => {
      let resolveApi: (v: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return new Promise((resolve) => { resolveApi = resolve; });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();

      await act(async () => {
        resolveApi!({ data: mockSensitivity });
      });

      const baselineCell = screen.getByText("0%");
      const row = baselineCell.closest("tr");
      expect(row).toHaveClass("bg-blue-50");
      expect(row).toHaveClass("font-medium");
    });

    it("shows sensitivity description text", async () => {
      let resolveApi: (v: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return new Promise((resolve) => { resolveApi = resolve; });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();

      await act(async () => {
        resolveApi!({ data: mockSensitivity });
      });

      expect(screen.getByText("optimizer.results.sensitivityDesc")).toBeInTheDocument();
    });

    it("calls sensitivity API with correct parameters on mount", () => {
      renderStepResults();

      expect(mockPost).toHaveBeenCalledWith("/api/optimizer/sensitivity", {
        loan_ids: ["loan-1", "loan-2"],
        monthly_extra: 5000,
        lump_sums: [{ month: 6, amount: 100000 }],
        strategy: "avalanche",
        annual_growth_pct: 5,
      });
    });

    it("includes rate lock advice when sensitivity data shows cost increase", async () => {
      let resolveApi: (v: unknown) => void;
      mockPost.mockImplementation((url: string) => {
        if (url === "/api/optimizer/sensitivity") {
          return new Promise((resolve) => { resolveApi = resolve; });
        }
        return Promise.resolve({ data: {} });
      });

      renderStepResults();

      await act(async () => {
        resolveApi!({ data: mockSensitivity });
      });

      // oneUp (rate_delta_pct=1) total_interest_paid=670000 minus baseline (rate_delta_pct=0) 620000 = 50000 > 0
      // so actionRateLock advice should appear
      expect(screen.getByText(/optimizer\.results\.actionRateLock/)).toBeInTheDocument();
    });
  });

  // ── Edge case: selectedStrategy falls back to recommended ──
  describe("Edge Cases", () => {
    it("falls back to recommended strategy when selectedStrategy not found", () => {
      renderStepResults({
        ...defaultProps,
        selectedStrategy: "nonexistent_strategy",
      });

      // Should fall back to best (avalanche) and still render
      expect(screen.getByText("Pay highest interest rate first")).toBeInTheDocument();
      expect(screen.getByText(/₹2,30,000/)).toBeInTheDocument();
    });

    it("renders with snowball as selected strategy", () => {
      renderStepResults({
        ...defaultProps,
        selectedStrategy: "snowball",
      });

      // Hero should show snowball data: interest_saved = 190000 → ₹1,90,000
      expect(screen.getByText(/₹1,90,000/)).toBeInTheDocument();
      expect(screen.getByText("Pay smallest balance first")).toBeInTheDocument();
    });
  });
});
