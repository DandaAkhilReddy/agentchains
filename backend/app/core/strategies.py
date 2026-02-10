"""Repayment strategy implementations for multi-loan optimization.

4 strategies:
- Avalanche: Highest interest rate first (mathematically optimal)
- Snowball: Lowest balance first (psychological wins)
- Smart Hybrid: Multi-factor scoring (effective rate + quick-win + foreclosure + balance)
- Proportional: Pro-rata by outstanding balance
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from dataclasses import dataclass


@dataclass
class LoanSnapshot:
    """Snapshot of a loan at a point in time during optimization."""
    loan_id: str
    bank_name: str
    loan_type: str  # home/personal/car/education/gold/credit_card/business
    outstanding_principal: Decimal
    interest_rate: Decimal  # Annual %
    emi_amount: Decimal
    remaining_tenure_months: int
    prepayment_penalty_pct: Decimal  # 0 for floating rate (RBI 2014)
    foreclosure_charges_pct: Decimal
    # Tax benefit fields — India
    eligible_80c: bool = False
    eligible_24b: bool = False
    eligible_80e: bool = False
    eligible_80eea: bool = False
    # Tax benefit fields — US
    eligible_mortgage_deduction: bool = False
    eligible_student_loan_deduction: bool = False
    # Derived
    effective_rate: Decimal = Decimal("0")  # Post-tax rate
    months_to_closure: int = 0  # Estimated months left


@dataclass
class LoanScore:
    """Composite score for SmartHybridStrategy multi-factor ranking."""
    loan_id: str
    effective_rate_score: float
    quick_win_score: float
    foreclosure_benefit_score: float
    balance_efficiency_score: float
    composite_score: float


# Scoring weights for SmartHybrid
WEIGHT_EFFECTIVE_RATE = 0.40
WEIGHT_QUICK_WIN = 0.25
WEIGHT_FORECLOSURE_BENEFIT = 0.20
WEIGHT_BALANCE_EFFICIENCY = 0.15


class RepaymentStrategy(ABC):
    """Base class for all repayment strategies."""

    name: str
    description: str

    @abstractmethod
    def allocate(
        self,
        active_loans: list[LoanSnapshot],
        extra_budget: Decimal,
    ) -> dict[str, Decimal]:
        """Allocate extra payment budget across active loans.

        Args:
            active_loans: Currently active (unpaid) loans
            extra_budget: Total extra money available this month

        Returns:
            Dict of {loan_id: extra_amount_to_pay}
        """
        ...


class AvalancheStrategy(RepaymentStrategy):
    """Pay highest interest rate loan first. Saves the most interest."""

    name = "avalanche"
    description = "Pay Least Interest — targets highest rate loan first"

    def allocate(self, active_loans: list[LoanSnapshot], extra_budget: Decimal) -> dict[str, Decimal]:
        if not active_loans or extra_budget <= 0:
            return {}

        # Sort by interest rate descending
        sorted_loans = sorted(active_loans, key=lambda l: l.interest_rate, reverse=True)
        allocation: dict[str, Decimal] = {}
        remaining = extra_budget

        for loan in sorted_loans:
            if remaining <= 0:
                break
            # Allocate up to outstanding principal (minus this month's EMI principal portion)
            max_prepayment = loan.outstanding_principal
            payment = min(remaining, max_prepayment)
            if payment > 0:
                allocation[loan.loan_id] = payment
                remaining -= payment

        return allocation


class SnowballStrategy(RepaymentStrategy):
    """Pay smallest balance loan first. Fastest psychological wins."""

    name = "snowball"
    description = "Fastest Quick Wins — eliminates smallest loan first"

    def allocate(self, active_loans: list[LoanSnapshot], extra_budget: Decimal) -> dict[str, Decimal]:
        if not active_loans or extra_budget <= 0:
            return {}

        # Sort by outstanding balance ascending
        sorted_loans = sorted(active_loans, key=lambda l: l.outstanding_principal)
        allocation: dict[str, Decimal] = {}
        remaining = extra_budget

        for loan in sorted_loans:
            if remaining <= 0:
                break
            max_prepayment = loan.outstanding_principal
            payment = min(remaining, max_prepayment)
            if payment > 0:
                allocation[loan.loan_id] = payment
                remaining -= payment

        return allocation


class SmartHybridStrategy(RepaymentStrategy):
    """Country-aware smart strategy using multi-factor composite scoring.

    Algorithm:
    1. Calculate post-tax effective_rate for each loan
    2. Score each loan across 4 factors (each 0-100, weighted):
       - Effective rate (40%): higher rate = higher score
       - Quick-win proximity (25%): closer to payoff = higher score
       - Foreclosure cost-benefit (20%): lower penalty = higher score
       - Balance efficiency (15%): smaller balance frees EMI sooner
    3. Sort by composite score DESC
    4. Breakeven gate: skip loans where foreclosure penalty > interest saved
    5. Allocate greedily by score order
    """

    name = "smart_hybrid"
    description = "Smart Hybrid (Recommended) — multi-factor scoring with tax optimization"

    def __init__(self, tax_bracket: Decimal = Decimal("0.30"), country: str = "IN"):
        self.tax_bracket = tax_bracket
        self.country = country

    def _calculate_effective_rate(self, loan: LoanSnapshot) -> Decimal:
        """Calculate post-tax effective interest rate (pure, no foreclosure adjustment)."""
        tax_benefit_rate = Decimal("0")

        if self.country == "US":
            if loan.eligible_mortgage_deduction:
                tax_benefit_rate = loan.interest_rate * self.tax_bracket
            elif loan.eligible_student_loan_deduction:
                tax_benefit_rate = loan.interest_rate * self.tax_bracket
        else:
            # India: Sections 80C, 24(b), 80E
            if loan.eligible_24b:
                tax_benefit_rate = loan.interest_rate * self.tax_bracket
            elif loan.eligible_80e:
                tax_benefit_rate = loan.interest_rate * self.tax_bracket
            elif loan.eligible_80c:
                tax_benefit_rate = loan.interest_rate * self.tax_bracket * Decimal("0.5")

        return loan.interest_rate - tax_benefit_rate

    def _estimate_months_to_closure(self, loan: LoanSnapshot, extra_per_month: Decimal) -> int:
        """Estimate how many months until this loan is paid off with extra payments."""
        if loan.emi_amount + extra_per_month <= 0:
            return 999

        r = loan.interest_rate / Decimal("1200")
        balance = loan.outstanding_principal
        months = 0
        total_monthly = loan.emi_amount + extra_per_month

        while balance > 0 and months < 600:
            interest = balance * r
            principal_paid = total_monthly - interest
            if principal_paid <= 0:
                return 999
            balance -= principal_paid
            months += 1

        return months

    def _passes_breakeven_check(self, loan: LoanSnapshot, prepayment_amount: Decimal) -> bool:
        """Return True if prepaying saves more interest than the penalty costs."""
        if loan.foreclosure_charges_pct <= 0:
            return True

        actual_prepay = min(prepayment_amount, loan.outstanding_principal)
        penalty_cost = actual_prepay * loan.foreclosure_charges_pct / 100

        monthly_rate = loan.interest_rate / Decimal("1200")
        months_remaining = min(loan.months_to_closure, loan.remaining_tenure_months)
        if months_remaining <= 0:
            months_remaining = 1

        # Conservative estimate: interest saved on reduced balance over remaining tenure
        interest_saved = actual_prepay * monthly_rate * Decimal(str(months_remaining)) / Decimal("2")

        return interest_saved >= penalty_cost

    def _score_loans(self, loans: list[LoanSnapshot], extra_budget: Decimal) -> list[LoanScore]:
        """Score each loan across 4 factors, each normalized 0-100."""
        if not loans:
            return []

        effective_rates = [float(l.effective_rate) for l in loans]
        months_list = [l.months_to_closure for l in loans]
        balances = [float(l.outstanding_principal) for l in loans]
        avg_remaining = sum(l.remaining_tenure_months for l in loans) / len(loans) if loans else 60

        # Dynamic quick-win threshold
        quick_win_threshold = max(2, min(6, int(avg_remaining * 0.05)))

        max_rate = max(effective_rates) if effective_rates else 1
        min_rate = min(effective_rates) if effective_rates else 0
        rate_range = max_rate - min_rate if max_rate != min_rate else 1

        max_balance = max(balances) if balances else 1
        min_balance = min(balances) if balances else 0
        balance_range = max_balance - min_balance if max_balance != min_balance else 1

        scores: list[LoanScore] = []
        for loan in loans:
            # Factor 1: Effective rate (higher = better to pay first)
            rate_score = ((float(loan.effective_rate) - min_rate) / rate_range) * 100

            # Factor 2: Quick-win proximity
            if loan.months_to_closure <= quick_win_threshold:
                qw_score = 100.0
            elif loan.months_to_closure <= quick_win_threshold * 2:
                qw_score = 50.0 * (1 - (loan.months_to_closure - quick_win_threshold) / max(quick_win_threshold, 1))
            else:
                qw_score = 0.0

            # Factor 3: Foreclosure cost-benefit
            fc_pct = float(loan.foreclosure_charges_pct)
            eff_rate = float(loan.effective_rate)
            if fc_pct <= 0:
                fc_score = 100.0
            elif eff_rate > 0:
                penalty_ratio = fc_pct / eff_rate
                fc_score = max(0.0, 100.0 * (1.0 - penalty_ratio))
            else:
                fc_score = 0.0

            # Factor 4: Balance efficiency (smaller frees EMI sooner)
            balance_score = ((max_balance - float(loan.outstanding_principal)) / balance_range) * 100 if balance_range > 0 else 50.0

            composite = (
                WEIGHT_EFFECTIVE_RATE * rate_score
                + WEIGHT_QUICK_WIN * qw_score
                + WEIGHT_FORECLOSURE_BENEFIT * fc_score
                + WEIGHT_BALANCE_EFFICIENCY * balance_score
            )

            scores.append(LoanScore(
                loan_id=loan.loan_id,
                effective_rate_score=rate_score,
                quick_win_score=qw_score,
                foreclosure_benefit_score=fc_score,
                balance_efficiency_score=balance_score,
                composite_score=composite,
            ))

        return scores

    def allocate(self, active_loans: list[LoanSnapshot], extra_budget: Decimal) -> dict[str, Decimal]:
        if not active_loans or extra_budget <= 0:
            return {}

        # Calculate effective rates and months to closure
        for loan in active_loans:
            loan.effective_rate = self._calculate_effective_rate(loan)
            loan.months_to_closure = self._estimate_months_to_closure(loan, Decimal("0"))

        # Score all loans with multi-factor model
        scores = self._score_loans(active_loans, extra_budget)
        sorted_ids = [s.loan_id for s in sorted(scores, key=lambda s: s.composite_score, reverse=True)]
        loan_map = {l.loan_id: l for l in active_loans}

        allocation: dict[str, Decimal] = {}
        remaining = extra_budget

        for loan_id in sorted_ids:
            if remaining <= 0:
                break
            loan = loan_map[loan_id]

            # Foreclosure breakeven gate
            if not self._passes_breakeven_check(loan, remaining):
                continue

            max_prepayment = loan.outstanding_principal
            payment = min(remaining, max_prepayment)
            if payment > 0:
                allocation[loan.loan_id] = payment
                remaining -= payment

        return allocation


class ProportionalStrategy(RepaymentStrategy):
    """Distribute extra payment proportionally by outstanding balance."""

    name = "proportional"
    description = "Balanced — distributes extra payment across all loans"

    def allocate(self, active_loans: list[LoanSnapshot], extra_budget: Decimal) -> dict[str, Decimal]:
        if not active_loans or extra_budget <= 0:
            return {}

        total_balance = sum(l.outstanding_principal for l in active_loans)
        if total_balance <= 0:
            return {}

        allocation: dict[str, Decimal] = {}
        allocated = Decimal("0")

        for i, loan in enumerate(active_loans):
            if loan.outstanding_principal <= 0:
                continue
            share = extra_budget * loan.outstanding_principal / total_balance
            share = share.quantize(Decimal("0.01"))
            allocation[loan.loan_id] = min(share, loan.outstanding_principal)
            allocated += allocation[loan.loan_id]

        # Assign rounding remainder to largest balance, capped at outstanding principal
        remainder = extra_budget - allocated
        if remainder > 0 and active_loans:
            largest = max(active_loans, key=lambda l: l.outstanding_principal)
            current = allocation.get(largest.loan_id, Decimal("0"))
            allocation[largest.loan_id] = current + min(remainder, largest.outstanding_principal - current)

        return allocation


def get_strategy(name: str, tax_bracket: Decimal = Decimal("0.30"), country: str = "IN") -> RepaymentStrategy:
    """Factory function to get strategy by name."""
    strategies = {
        "avalanche": AvalancheStrategy(),
        "snowball": SnowballStrategy(),
        "smart_hybrid": SmartHybridStrategy(tax_bracket, country),
        "proportional": ProportionalStrategy(),
    }
    if name not in strategies:
        raise ValueError(f"Unknown strategy: {name}. Choose from: {list(strategies.keys())}")
    return strategies[name]
