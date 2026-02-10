import { describe, it, expect } from "vitest";
import {
  calculateEMI,
  calculateTotalInterest,
  generateAmortization,
  calculateInterestSaved,
  reverseEMIRate,
  calculateAffordability,
} from "../emi-math";

describe("calculateEMI", () => {
  it("computes SBI home loan benchmark: 50L at 8.5% for 20 years", () => {
    expect(calculateEMI(5_000_000, 8.5, 240)).toBe(43391);
  });

  it("returns principal/tenure when rate is zero", () => {
    expect(calculateEMI(1_200_000, 0, 120)).toBe(10000);
  });

  it("returns 0 when principal is zero", () => {
    expect(calculateEMI(0, 8.5, 240)).toBe(0);
  });

  it("returns 0 when tenure is zero", () => {
    expect(calculateEMI(5_000_000, 8.5, 0)).toBe(0);
  });
});

describe("calculateTotalInterest", () => {
  it("returns significant interest for a standard home loan", () => {
    const interest = calculateTotalInterest(5_000_000, 8.5, 240);
    expect(interest).toBeGreaterThan(0);
    // Total interest on 50L at 8.5% for 20y is roughly 54L
    expect(interest).toBeGreaterThan(5_000_000);
  });

  it("returns 0 when rate is zero", () => {
    expect(calculateTotalInterest(1_200_000, 0, 120)).toBe(0);
  });

  it("equals emi * tenure - principal", () => {
    const principal = 5_000_000;
    const rate = 8.5;
    const tenure = 240;
    const emi = calculateEMI(principal, rate, tenure);
    const totalInterest = calculateTotalInterest(principal, rate, tenure);
    expect(totalInterest).toBe(emi * tenure - principal);
  });
});

describe("generateAmortization", () => {
  it("produces a schedule with length equal to tenure (no prepayment)", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    expect(schedule.length).toBe(240);
  });

  it("has higher interest than principal portion in the first month", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    expect(schedule[0].interest).toBeGreaterThan(schedule[0].principal);
  });

  it("ends with a near-zero balance (rounding residual only)", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    // Month-by-month Math.round on interest can leave a small residual;
    // it must be negligible relative to the original principal.
    expect(schedule[schedule.length - 1].balance).toBeLessThanOrEqual(500);
  });

  it("cumulative interest in last entry equals calculateTotalInterest", () => {
    const principal = 5_000_000;
    const rate = 8.5;
    const tenure = 240;
    const schedule = generateAmortization(principal, rate, tenure);
    const totalInterest = calculateTotalInterest(principal, rate, tenure);
    const cumulativeInterest = schedule[schedule.length - 1].cumulativeInterest;
    // Allow rounding tolerance of 1 rupee per month
    expect(Math.abs(cumulativeInterest - totalInterest)).toBeLessThanOrEqual(tenure);
  });

  it("shortens the schedule when a monthly prepayment is applied", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240, 5000);
    expect(schedule.length).toBeLessThan(240);
  });
});

describe("calculateInterestSaved", () => {
  it("reports positive savings with a monthly prepayment", () => {
    const { interestSaved, monthsSaved } = calculateInterestSaved(5_000_000, 8.5, 240, 5000);
    expect(interestSaved).toBeGreaterThan(0);
    expect(monthsSaved).toBeGreaterThan(0);
  });

  it("reports near-zero savings with no prepayment", () => {
    const { interestSaved, monthsSaved } = calculateInterestSaved(5_000_000, 8.5, 240, 0);
    // Rounding residual between calculateTotalInterest and amortization schedule;
    // the difference must be negligible (within a few hundred rupees).
    expect(Math.abs(interestSaved)).toBeLessThanOrEqual(500);
    expect(monthsSaved).toBe(0);
  });
});

describe("reverseEMIRate", () => {
  it("recovers the original rate from a known EMI (roundtrip)", () => {
    const emi = calculateEMI(5_000_000, 8.5, 240);
    const recoveredRate = reverseEMIRate(5_000_000, emi, 240);
    expect(recoveredRate).toBeCloseTo(8.5, 1);
  });

  it("converges within +/-0.1% of the expected rate", () => {
    const expectedRate = 10.0;
    const emi = calculateEMI(3_000_000, expectedRate, 180);
    const recoveredRate = reverseEMIRate(3_000_000, emi, 180);
    expect(Math.abs(recoveredRate - expectedRate)).toBeLessThanOrEqual(0.1);
  });
});

describe("calculateAffordability", () => {
  it("returns approximately the original principal (inverse of EMI)", () => {
    const affordable = calculateAffordability(43391, 8.5, 240);
    // Should be close to 50L; allow 0.1% tolerance
    expect(Math.abs(affordable - 5_000_000)).toBeLessThanOrEqual(5_000_000 * 0.001);
  });

  it("returns emi * tenure when rate is zero", () => {
    expect(calculateAffordability(10000, 0, 120)).toBe(1_200_000);
  });
});

// ---------------------------------------------------------------------------
// Edge-case test suites
// ---------------------------------------------------------------------------

describe("Edge: very high interest rate (30%)", () => {
  const principal = 1_000_000;
  const rate = 30;
  const tenure = 120; // 10 years

  it("calculateEMI returns a value greater than simple division", () => {
    const emi = calculateEMI(principal, rate, tenure);
    // At 30%, EMI should be much higher than principal/tenure
    expect(emi).toBeGreaterThan(principal / tenure);
    // Monthly rate = 2.5%, so first-month interest alone = 25,000
    expect(emi).toBeGreaterThan(25_000);
  });

  it("total interest far exceeds the principal at 30%", () => {
    const totalInterest = calculateTotalInterest(principal, rate, tenure);
    // At 30% for 10y, total interest should exceed 2x the principal
    expect(totalInterest).toBeGreaterThan(principal * 2);
  });

  it("amortization schedule starts with interest dominating", () => {
    const schedule = generateAmortization(principal, rate, tenure);
    // First month interest = round(1_000_000 * 0.025) = 25_000
    expect(schedule[0].interest).toBe(25_000);
    expect(schedule[0].interest).toBeGreaterThan(schedule[0].principal);
  });

  it("amortization schedule closes out by tenure end", () => {
    const schedule = generateAmortization(principal, rate, tenure);
    expect(schedule.length).toBe(tenure);
    expect(schedule[schedule.length - 1].balance).toBeLessThanOrEqual(500);
  });
});

describe("Edge: very long tenure (600 months / 50 years)", () => {
  const principal = 5_000_000;
  const rate = 8.5;
  const tenure = 600;

  it("calculateEMI returns a positive, finite value", () => {
    const emi = calculateEMI(principal, rate, tenure);
    expect(emi).toBeGreaterThan(0);
    expect(Number.isFinite(emi)).toBe(true);
  });

  it("EMI for 600 months is lower than EMI for 240 months (same P & r)", () => {
    const emi600 = calculateEMI(principal, rate, tenure);
    const emi240 = calculateEMI(principal, rate, 240);
    expect(emi600).toBeLessThan(emi240);
  });

  it("total interest grows dramatically for 50-year tenure", () => {
    const interest600 = calculateTotalInterest(principal, rate, tenure);
    const interest240 = calculateTotalInterest(principal, rate, 240);
    expect(interest600).toBeGreaterThan(interest240);
    // Should be several times the principal
    expect(interest600).toBeGreaterThan(principal * 3);
  });

  it("amortization schedule has exactly 600 entries", () => {
    const schedule = generateAmortization(principal, rate, tenure);
    expect(schedule.length).toBe(600);
  });
});

describe("Edge: very short tenure (1 month)", () => {
  const principal = 100_000;

  it("EMI equals principal + one month of interest", () => {
    const rate = 12; // Monthly rate = 1%
    const emi = calculateEMI(principal, rate, 1);
    // EMI should be principal + 1% interest = 101,000
    expect(emi).toBe(101_000);
  });

  it("total interest is exactly one month of interest", () => {
    const rate = 12;
    const totalInterest = calculateTotalInterest(principal, rate, 1);
    expect(totalInterest).toBe(1_000); // 100_000 * 0.01
  });

  it("amortization schedule has exactly 1 entry", () => {
    const schedule = generateAmortization(principal, 12, 1);
    expect(schedule.length).toBe(1);
    expect(schedule[0].month).toBe(1);
    expect(schedule[0].balance).toBe(0);
  });

  it("zero-rate single-month tenure returns principal as EMI", () => {
    expect(calculateEMI(100_000, 0, 1)).toBe(100_000);
  });
});

describe("Edge: zero interest rate", () => {
  const principal = 2_400_000;
  const tenure = 240;

  it("EMI is exactly principal / tenure", () => {
    expect(calculateEMI(principal, 0, tenure)).toBe(10_000);
  });

  it("total interest is exactly zero", () => {
    expect(calculateTotalInterest(principal, 0, tenure)).toBe(0);
  });

  it("every amortization entry has zero interest", () => {
    const schedule = generateAmortization(principal, 0, tenure);
    schedule.forEach((entry) => {
      expect(entry.interest).toBe(0);
    });
  });

  it("balance decreases linearly each month", () => {
    const schedule = generateAmortization(principal, 0, tenure);
    for (let i = 0; i < schedule.length; i++) {
      const expectedBalance = principal - (i + 1) * (principal / tenure);
      expect(schedule[i].balance).toBe(expectedBalance);
    }
  });

  it("prepayment still shortens zero-rate loan", () => {
    const schedule = generateAmortization(principal, 0, tenure, 5_000);
    // EMI is 10,000 + prepay 5,000 = 15,000/month principal reduction
    // 2,400,000 / 15,000 = 160 months
    expect(schedule.length).toBe(160);
  });
});

describe("Edge: very small principal (Rs 100)", () => {
  it("calculateEMI works for tiny principal", () => {
    const emi = calculateEMI(100, 12, 12);
    expect(emi).toBeGreaterThan(0);
    expect(Number.isFinite(emi)).toBe(true);
  });

  it("total interest is small but non-negative", () => {
    const interest = calculateTotalInterest(100, 12, 12);
    expect(interest).toBeGreaterThanOrEqual(0);
  });

  it("amortization schedule still runs to completion", () => {
    const schedule = generateAmortization(100, 12, 12);
    expect(schedule.length).toBeGreaterThan(0);
    expect(schedule.length).toBeLessThanOrEqual(12);
    expect(schedule[schedule.length - 1].balance).toBe(0);
  });

  it("reverse EMI degrades gracefully for tiny principal", () => {
    // With Rs 100 principal, EMI rounds to ~9. Integer rounding creates
    // wide rate-plateaus (many rates map to the same EMI), so we can
    // only assert that reverseEMIRate finishes without error and returns
    // a positive finite number. Precision improves for larger principals.
    const emi = calculateEMI(100, 12, 12);
    const recovered = reverseEMIRate(100, emi, 12);
    expect(recovered).toBeGreaterThan(0);
    expect(Number.isFinite(recovered)).toBe(true);
  });
});

describe("Edge: very large principal (Rs 10 crore = 100_000_000)", () => {
  const principal = 100_000_000;
  const rate = 8.5;
  const tenure = 360; // 30 years

  it("calculateEMI returns a value in a sensible range", () => {
    const emi = calculateEMI(principal, rate, tenure);
    expect(emi).toBeGreaterThan(700_000); // At least ~7.7L/month
    expect(emi).toBeLessThan(1_000_000); // Less than 10L/month
    expect(Number.isFinite(emi)).toBe(true);
  });

  it("total interest is proportional to principal", () => {
    const interest = calculateTotalInterest(principal, rate, tenure);
    // At 8.5% for 30y, total interest roughly 1.76x principal
    expect(interest).toBeGreaterThan(principal);
    expect(interest).toBeLessThan(principal * 3);
  });

  it("amortization schedule completes with 360 entries", () => {
    const schedule = generateAmortization(principal, rate, tenure);
    expect(schedule.length).toBe(360);
    expect(schedule[schedule.length - 1].balance).toBeLessThanOrEqual(1000);
  });

  it("affordability roundtrips accurately for large amounts", () => {
    const emi = calculateEMI(principal, rate, tenure);
    const recoveredPrincipal = calculateAffordability(emi, rate, tenure);
    // Within 0.1% of original
    expect(Math.abs(recoveredPrincipal - principal)).toBeLessThanOrEqual(
      principal * 0.001,
    );
  });
});

describe("Edge: reverse EMI calculation accuracy", () => {
  const testCases = [
    { principal: 500_000, rate: 7.0, tenure: 60 },
    { principal: 2_000_000, rate: 9.5, tenure: 180 },
    { principal: 10_000_000, rate: 12.0, tenure: 240 },
    { principal: 50_000, rate: 18.0, tenure: 36 },
    { principal: 100_000_000, rate: 6.5, tenure: 360 },
  ];

  testCases.forEach(({ principal, rate, tenure }) => {
    it(`roundtrips for P=${principal}, r=${rate}%, n=${tenure}m`, () => {
      const emi = calculateEMI(principal, rate, tenure);
      const recovered = reverseEMIRate(principal, emi, tenure);
      expect(Math.abs(recovered - rate)).toBeLessThanOrEqual(0.1);
    });
  });

  it("returns a rate close to the upper bound for extreme EMIs", () => {
    // EMI almost equals principal means very high rate
    const recovered = reverseEMIRate(100_000, 99_000, 2);
    expect(recovered).toBeGreaterThan(0);
    expect(Number.isFinite(recovered)).toBe(true);
  });

  it("handles near-zero EMI (close to interest-only)", () => {
    // An EMI that barely covers interest at ~8.5% on 10L
    // Monthly interest = 10L * 8.5/1200 ~= 7083
    // EMI just above that
    const recovered = reverseEMIRate(1_000_000, 7100, 360);
    expect(recovered).toBeGreaterThan(0);
    expect(recovered).toBeLessThan(10);
  });
});

describe("Edge: affordability calculation", () => {
  it("returns 0 for zero or negative EMI", () => {
    expect(calculateAffordability(0, 8.5, 240)).toBe(0);
    expect(calculateAffordability(-1000, 8.5, 240)).toBe(0);
  });

  it("returns 0 for zero tenure", () => {
    expect(calculateAffordability(10_000, 8.5, 0)).toBe(0);
  });

  it("higher EMI affords more principal (same rate & tenure)", () => {
    const a1 = calculateAffordability(20_000, 8.5, 240);
    const a2 = calculateAffordability(40_000, 8.5, 240);
    expect(a2).toBeGreaterThan(a1);
    // Should be approximately double
    expect(Math.abs(a2 - 2 * a1)).toBeLessThanOrEqual(a1 * 0.01);
  });

  it("lower rate affords more principal (same EMI & tenure)", () => {
    const affordLow = calculateAffordability(50_000, 7.0, 240);
    const affordHigh = calculateAffordability(50_000, 12.0, 240);
    expect(affordLow).toBeGreaterThan(affordHigh);
  });

  it("longer tenure affords more principal (same EMI & rate)", () => {
    const afford120 = calculateAffordability(50_000, 8.5, 120);
    const afford360 = calculateAffordability(50_000, 8.5, 360);
    expect(afford360).toBeGreaterThan(afford120);
  });

  it("roundtrips accurately for common Indian home loan", () => {
    // 30L at 8.5% for 20y
    const principal = 3_000_000;
    const emi = calculateEMI(principal, 8.5, 240);
    const recovered = calculateAffordability(emi, 8.5, 240);
    expect(Math.abs(recovered - principal)).toBeLessThanOrEqual(principal * 0.001);
  });
});

describe("Edge: prepayment savings calculation", () => {
  it("larger prepayment saves more interest and months", () => {
    const small = calculateInterestSaved(5_000_000, 8.5, 240, 2_000);
    const large = calculateInterestSaved(5_000_000, 8.5, 240, 10_000);
    expect(large.interestSaved).toBeGreaterThan(small.interestSaved);
    expect(large.monthsSaved).toBeGreaterThan(small.monthsSaved);
  });

  it("prepayment equal to EMI roughly halves the tenure", () => {
    const emi = calculateEMI(5_000_000, 8.5, 240);
    const result = calculateInterestSaved(5_000_000, 8.5, 240, emi);
    // Prepaying an amount equal to the EMI each month should cut
    // the tenure to roughly half or less
    expect(result.monthsSaved).toBeGreaterThan(100);
  });

  it("prepayment on zero-rate loan saves zero interest", () => {
    const result = calculateInterestSaved(1_200_000, 0, 120, 5_000);
    expect(result.interestSaved).toBe(0);
    // But it should still shorten the tenure
    expect(result.monthsSaved).toBeGreaterThan(0);
  });

  it("very large prepayment clears the loan almost immediately", () => {
    // Prepayment much larger than EMI
    const result = calculateInterestSaved(1_000_000, 8.5, 240, 500_000);
    expect(result.monthsSaved).toBeGreaterThan(230);
    // Barely any interest accrued
    expect(result.interestSaved).toBeGreaterThan(0);
  });

  it("interestSaved is always non-negative for valid prepayments", () => {
    const result = calculateInterestSaved(5_000_000, 8.5, 240, 1);
    expect(result.interestSaved).toBeGreaterThanOrEqual(0);
    expect(result.monthsSaved).toBeGreaterThanOrEqual(0);
  });
});

describe("Edge: monthly vs yearly amortization consistency", () => {
  it("12 consecutive months of interest sum close to first year interest", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    const firstYearInterest = schedule
      .slice(0, 12)
      .reduce((sum, e) => sum + e.interest, 0);
    // First-year interest on 50L at 8.5% should be ~4.2L
    // (declining each month, so a bit less than 50L * 8.5% = 4.25L)
    expect(firstYearInterest).toBeGreaterThan(400_000);
    expect(firstYearInterest).toBeLessThanOrEqual(425_000);
  });

  it("cumulative interest grows monotonically through the schedule", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    for (let i = 1; i < schedule.length; i++) {
      expect(schedule[i].cumulativeInterest).toBeGreaterThanOrEqual(
        schedule[i - 1].cumulativeInterest,
      );
    }
  });

  it("balance is strictly non-increasing through the schedule", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    for (let i = 1; i < schedule.length; i++) {
      expect(schedule[i].balance).toBeLessThanOrEqual(schedule[i - 1].balance);
    }
  });

  it("principal portion grows over time (normal amortization curve)", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    // Compare first month vs halfway vs last month principal portions
    const firstPrincipal = schedule[0].principal;
    const midPrincipal = schedule[119].principal;
    const lastPrincipal = schedule[schedule.length - 1].principal;
    expect(midPrincipal).toBeGreaterThan(firstPrincipal);
    expect(lastPrincipal).toBeGreaterThan(midPrincipal);
  });

  it("sum of all principal portions equals the original principal", () => {
    const principal = 5_000_000;
    const schedule = generateAmortization(principal, 8.5, 240);
    const totalPrincipalPaid = schedule.reduce((sum, e) => sum + e.principal, 0);
    // Allow small rounding tolerance (1 rupee per month maximum)
    expect(Math.abs(totalPrincipalPaid - principal)).toBeLessThanOrEqual(240);
  });

  it("interest portion decreases over time (normal amortization curve)", () => {
    const schedule = generateAmortization(5_000_000, 8.5, 240);
    const firstInterest = schedule[0].interest;
    const midInterest = schedule[119].interest;
    const lastInterest = schedule[schedule.length - 1].interest;
    expect(midInterest).toBeLessThan(firstInterest);
    expect(lastInterest).toBeLessThan(midInterest);
  });
});
