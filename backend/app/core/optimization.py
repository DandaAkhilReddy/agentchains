"""Multi-loan month-by-month optimization engine with freed-EMI rollover.

THE core differentiator: simulates paying off multiple loans simultaneously,
applying different strategies, and rolling freed EMIs into remaining loans.

Max simulation: 600 months (50 years).
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from copy import deepcopy

from app.core.strategies import LoanSnapshot, RepaymentStrategy, get_strategy


PAISA = Decimal("0.01")


@dataclass
class MonthlySnapshot:
    """State of all loans at a specific month."""
    month: int
    total_balance: Decimal
    total_interest_paid: Decimal
    total_principal_paid: Decimal
    total_prepayment: Decimal
    freed_emi_pool: Decimal
    loans_active: int
    loans_paid_off: list[str] = field(default_factory=list)
    allocations: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class LoanResult:
    """Final result for a single loan within the optimization."""
    loan_id: str
    bank_name: str
    loan_type: str
    original_balance: Decimal
    total_interest_paid: Decimal
    total_principal_paid: Decimal
    total_prepayment: Decimal
    payoff_month: int
    months_saved: int  # vs baseline (no extra payments)


@dataclass
class StrategyResult:
    """Complete result of running one strategy."""
    strategy_name: str
    strategy_description: str
    total_interest_paid: Decimal
    total_months: int
    interest_saved_vs_baseline: Decimal
    months_saved_vs_baseline: int
    payoff_order: list[str]  # loan_ids in order they were paid off
    loan_results: list[LoanResult]
    monthly_snapshots: list[MonthlySnapshot]
    debt_free_date_months: int  # Month number when all loans are paid


@dataclass
class OptimizationResult:
    """Results comparing all strategies."""
    baseline_total_interest: Decimal
    baseline_total_months: int
    strategies: list[StrategyResult]
    recommended_strategy: str


@dataclass
class SensitivityPoint:
    """Result at one rate delta."""
    rate_delta_pct: float
    total_interest_paid: Decimal
    total_months: int
    interest_saved_vs_baseline: Decimal


@dataclass
class SensitivityResult:
    """Rate sensitivity analysis results."""
    strategy_name: str
    points: list[SensitivityPoint]


class MultiLoanOptimizer:
    """Month-by-month multi-loan simulator with freed-EMI rollover.

    The "relay race" effect: when Loan A pays off, its EMI gets added to
    the extra budget for Loan B, creating an accelerating payoff cascade.
    """

    MAX_MONTHS = 600

    def __init__(
        self,
        loans: list[LoanSnapshot],
        monthly_extra: Decimal = Decimal("0"),
        lump_sums: dict[int, Decimal] | None = None,
        annual_growth_pct: Decimal = Decimal("0"),
    ):
        self.original_loans = loans
        self.monthly_extra = monthly_extra
        self.lump_sums = lump_sums or {}
        self.annual_growth_pct = annual_growth_pct

    def _simulate_baseline(self) -> tuple[Decimal, int]:
        """Simulate all loans with minimum payments only (no extra)."""
        loans = deepcopy(self.original_loans)
        total_interest = Decimal("0")
        max_month = 0

        for loan in loans:
            r = loan.interest_rate / Decimal("1200")
            balance = loan.outstanding_principal

            for month in range(1, self.MAX_MONTHS + 1):
                if balance <= 0:
                    break
                interest = (balance * r).quantize(PAISA, ROUND_HALF_UP)
                principal = loan.emi_amount - interest
                if principal <= 0:
                    break  # EMI doesn't cover interest
                if principal > balance:
                    principal = balance
                balance -= principal
                total_interest += interest
                max_month = max(max_month, month)

        return total_interest, max_month

    def _simulate_strategy(self, strategy: RepaymentStrategy) -> StrategyResult:
        """Run full month-by-month simulation with a given strategy."""
        loans = deepcopy(self.original_loans)
        original_balances = {l.loan_id: l.outstanding_principal for l in loans}
        original_tenures = {l.loan_id: l.remaining_tenure_months for l in loans}

        freed_emi_pool = Decimal("0")
        total_interest = Decimal("0")
        total_principal = Decimal("0")
        total_prepayment = Decimal("0")

        monthly_snapshots: list[MonthlySnapshot] = []
        loan_results: dict[str, LoanResult] = {}
        payoff_order: list[str] = []

        for month in range(1, self.MAX_MONTHS + 1):
            active_loans = [l for l in loans if l.outstanding_principal > 0]
            if not active_loans:
                break

            month_interest = Decimal("0")
            month_principal = Decimal("0")
            month_prepayment = Decimal("0")
            loans_paid_this_month: list[str] = []

            # Step 1: Apply regular EMI to each active loan
            for loan in active_loans:
                r = loan.interest_rate / Decimal("1200")
                interest = (loan.outstanding_principal * r).quantize(PAISA, ROUND_HALF_UP)
                principal_portion = loan.emi_amount - interest

                if principal_portion > loan.outstanding_principal:
                    principal_portion = loan.outstanding_principal

                loan.outstanding_principal -= principal_portion
                month_interest += interest
                month_principal += principal_portion

            # Step 2: Calculate extra budget (with salary growth)
            growth_multiplier = Decimal(str(
                (1 + float(self.annual_growth_pct) / 100) ** ((month - 1) // 12)
            ))
            grown_extra = (self.monthly_extra * growth_multiplier).quantize(PAISA, ROUND_HALF_UP)
            lump_sum_this_month = self.lump_sums.get(month, Decimal("0"))
            extra = grown_extra + freed_emi_pool + lump_sum_this_month

            # Step 3: Allocate extra across active loans using strategy
            still_active = [l for l in loans if l.outstanding_principal > 0]
            if extra > 0 and still_active:
                allocations = strategy.allocate(still_active, extra)

                for loan_id, amount in allocations.items():
                    loan = next((l for l in loans if l.loan_id == loan_id), None)
                    if loan and loan.outstanding_principal > 0:
                        # Apply prepayment penalty for fixed-rate loans
                        actual_payment = min(amount, loan.outstanding_principal)
                        penalty = (actual_payment * loan.prepayment_penalty_pct / 100).quantize(PAISA, ROUND_HALF_UP)
                        net_payment = actual_payment - penalty

                        if net_payment > 0:
                            loan.outstanding_principal -= net_payment
                            month_prepayment += actual_payment
            else:
                allocations = {}

            # Step 4: Check for newly paid-off loans
            for loan in loans:
                if loan.outstanding_principal <= 0 and loan.loan_id not in payoff_order:
                    loan.outstanding_principal = Decimal("0")
                    payoff_order.append(loan.loan_id)
                    loans_paid_this_month.append(loan.loan_id)
                    freed_emi_pool += loan.emi_amount  # The relay race effect!

                    # Calculate baseline months for this loan
                    baseline_months = original_tenures.get(loan.loan_id, month)

                    loan_results[loan.loan_id] = LoanResult(
                        loan_id=loan.loan_id,
                        bank_name=loan.bank_name,
                        loan_type=loan.loan_type,
                        original_balance=original_balances[loan.loan_id],
                        total_interest_paid=Decimal("0"),  # Tracked globally
                        total_principal_paid=original_balances[loan.loan_id],
                        total_prepayment=Decimal("0"),
                        payoff_month=month,
                        months_saved=max(0, baseline_months - month),
                    )

            total_interest += month_interest
            total_principal += month_principal
            total_prepayment += month_prepayment

            total_balance = sum(l.outstanding_principal for l in loans)

            monthly_snapshots.append(MonthlySnapshot(
                month=month,
                total_balance=total_balance,
                total_interest_paid=total_interest,
                total_principal_paid=total_principal,
                total_prepayment=total_prepayment,
                freed_emi_pool=freed_emi_pool,
                loans_active=len([l for l in loans if l.outstanding_principal > 0]),
                loans_paid_off=loans_paid_this_month,
                allocations={k: v for k, v in allocations.items()},
            ))

            if total_balance <= 0:
                break

        last_month = monthly_snapshots[-1].month if monthly_snapshots else 0

        return StrategyResult(
            strategy_name=strategy.name,
            strategy_description=strategy.description,
            total_interest_paid=total_interest,
            total_months=last_month,
            interest_saved_vs_baseline=Decimal("0"),  # Set after baseline calc
            months_saved_vs_baseline=0,
            payoff_order=payoff_order,
            loan_results=list(loan_results.values()),
            monthly_snapshots=monthly_snapshots,
            debt_free_date_months=last_month,
        )

    def optimize(
        self,
        strategies: list[str] | None = None,
        tax_bracket: Decimal = Decimal("0.30"),
        country: str = "IN",
    ) -> OptimizationResult:
        """Run all strategies and compare results.

        Args:
            strategies: List of strategy names. Default: all 4.
            tax_bracket: User's income tax bracket for SmartHybrid.
            country: 'IN' or 'US' for country-aware tax calculations.

        Returns:
            OptimizationResult with all strategies compared.
        """
        if strategies is None:
            strategies = ["avalanche", "snowball", "smart_hybrid", "proportional"]

        # Calculate baseline (no extra payments)
        baseline_interest, baseline_months = self._simulate_baseline()

        # Run each strategy
        results: list[StrategyResult] = []
        for strategy_name in strategies:
            strategy = get_strategy(strategy_name, tax_bracket, country)
            result = self._simulate_strategy(strategy)
            result.interest_saved_vs_baseline = (
                baseline_interest - result.total_interest_paid
            ).quantize(PAISA, ROUND_HALF_UP)
            result.months_saved_vs_baseline = baseline_months - result.total_months
            results.append(result)

        # Find recommended strategy (most interest saved)
        best = max(results, key=lambda r: r.interest_saved_vs_baseline)

        return OptimizationResult(
            baseline_total_interest=baseline_interest,
            baseline_total_months=baseline_months,
            strategies=results,
            recommended_strategy=best.strategy_name,
        )

    def sensitivity_analysis(
        self,
        strategy_name: str = "smart_hybrid",
        rate_deltas: list[float] | None = None,
        tax_bracket: Decimal = Decimal("0.30"),
        country: str = "IN",
    ) -> SensitivityResult:
        """Run a strategy at multiple rate deltas to show interest rate sensitivity.

        Args:
            strategy_name: Strategy to analyze.
            rate_deltas: Rate adjustments in percentage points, e.g. [-1, 0, +1, +2].
            tax_bracket: Tax bracket for SmartHybrid.
            country: Country code.

        Returns:
            SensitivityResult with interest/months at each delta.
        """
        if rate_deltas is None:
            rate_deltas = [-1.0, 0.0, 1.0, 2.0]

        points: list[SensitivityPoint] = []

        for delta in rate_deltas:
            adjusted_loans = deepcopy(self.original_loans)
            for loan in adjusted_loans:
                new_rate = loan.interest_rate + Decimal(str(delta))
                loan.interest_rate = max(new_rate, Decimal("0.1"))

            temp_optimizer = MultiLoanOptimizer(
                loans=adjusted_loans,
                monthly_extra=self.monthly_extra,
                lump_sums=self.lump_sums,
                annual_growth_pct=self.annual_growth_pct,
            )

            result = temp_optimizer.optimize(
                strategies=[strategy_name],
                tax_bracket=tax_bracket,
                country=country,
            )

            strat = result.strategies[0]
            points.append(SensitivityPoint(
                rate_delta_pct=delta,
                total_interest_paid=strat.total_interest_paid,
                total_months=strat.total_months,
                interest_saved_vs_baseline=strat.interest_saved_vs_baseline,
            ))

        return SensitivityResult(strategy_name=strategy_name, points=points)
