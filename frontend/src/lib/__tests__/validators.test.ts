import { describe, it, expect } from "vitest";
import { loanSchema, emiCalculatorSchema } from "../validators";

const validLoan = {
  bank_name: "SBI",
  loan_type: "home" as const,
  principal_amount: 5000000,
  outstanding_principal: 4500000,
  interest_rate: 8.5,
  tenure_months: 240,
  remaining_tenure_months: 220,
  emi_amount: 43391,
};

describe("loanSchema", () => {
  it("valid full object passes", () => {
    const result = loanSchema.parse(validLoan);
    expect(result).toEqual(
      expect.objectContaining({
        bank_name: "SBI",
        loan_type: "home",
        principal_amount: 5000000,
        outstanding_principal: 4500000,
        interest_rate: 8.5,
        tenure_months: 240,
        remaining_tenure_months: 220,
        emi_amount: 43391,
      })
    );
  });

  it("missing bank_name fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, bank_name: "" })
    ).toThrow();
  });

  it("negative principal fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, principal_amount: -1000 })
    ).toThrow();
  });

  it("interest rate above 50 fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, interest_rate: 55 })
    ).toThrow();
  });

  it("tenure above 600 fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, tenure_months: 700 })
    ).toThrow();
  });

  it("emi_due_date above 28 fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, emi_due_date: 35 })
    ).toThrow();
  });

  it("default values applied", () => {
    const result = loanSchema.parse(validLoan);
    expect(result.interest_rate_type).toBe("floating");
    expect(result.eligible_80c).toBe(false);
    expect(result.eligible_24b).toBe(false);
    expect(result.eligible_80e).toBe(false);
    expect(result.eligible_80eea).toBe(false);
    expect(result.prepayment_penalty_pct).toBe(0);
    expect(result.foreclosure_charges_pct).toBe(0);
  });
});

describe("emiCalculatorSchema", () => {
  it("valid object passes", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 8.5,
      tenure_months: 240,
    });
    expect(result).toEqual(
      expect.objectContaining({
        principal: 5000000,
        annual_rate: 8.5,
        tenure_months: 240,
      })
    );
  });

  it("negative prepayment fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: 8.5,
        tenure_months: 240,
        monthly_prepayment: -100,
      })
    ).toThrow();
  });

  it("default prepayment is 0", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 8.5,
      tenure_months: 240,
    });
    expect(result.monthly_prepayment).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Extended loanSchema tests
// ---------------------------------------------------------------------------
describe("loanSchema — loan amount validation", () => {
  it("zero principal fails (must be positive)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, principal_amount: 0 })
    ).toThrow();
  });

  it("very small positive principal passes", () => {
    const result = loanSchema.parse({ ...validLoan, principal_amount: 1 });
    expect(result.principal_amount).toBe(1);
  });

  it("very large principal passes (no upper cap in schema)", () => {
    const result = loanSchema.parse({
      ...validLoan,
      principal_amount: 999_999_999_999,
    });
    expect(result.principal_amount).toBe(999_999_999_999);
  });

  it("string principal fails type check", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, principal_amount: "5000000" })
    ).toThrow();
  });

  it("null principal fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, principal_amount: null })
    ).toThrow();
  });

  it("undefined principal fails (field is required)", () => {
    const { principal_amount, ...rest } = validLoan;
    expect(() => loanSchema.parse(rest)).toThrow();
  });
});

describe("loanSchema — outstanding principal validation", () => {
  it("zero outstanding principal passes", () => {
    const result = loanSchema.parse({
      ...validLoan,
      outstanding_principal: 0,
    });
    expect(result.outstanding_principal).toBe(0);
  });

  it("negative outstanding principal fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, outstanding_principal: -1 })
    ).toThrow();
  });
});

describe("loanSchema — interest rate validation", () => {
  it("zero interest rate passes (boundary)", () => {
    const result = loanSchema.parse({ ...validLoan, interest_rate: 0 });
    expect(result.interest_rate).toBe(0);
  });

  it("negative interest rate fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, interest_rate: -0.5 })
    ).toThrow();
  });

  it("exact 50% passes (boundary)", () => {
    const result = loanSchema.parse({ ...validLoan, interest_rate: 50 });
    expect(result.interest_rate).toBe(50);
  });

  it("50.01% fails (just above max)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, interest_rate: 50.01 })
    ).toThrow();
  });

  it("100% fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, interest_rate: 100 })
    ).toThrow();
  });

  it("fractional rate like 7.25 passes", () => {
    const result = loanSchema.parse({ ...validLoan, interest_rate: 7.25 });
    expect(result.interest_rate).toBe(7.25);
  });

  it("string interest rate fails type check", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, interest_rate: "8.5" })
    ).toThrow();
  });
});

describe("loanSchema — tenure validation", () => {
  it("tenure of 1 month passes (minimum boundary)", () => {
    const result = loanSchema.parse({
      ...validLoan,
      tenure_months: 1,
      remaining_tenure_months: 1,
    });
    expect(result.tenure_months).toBe(1);
  });

  it("tenure of 600 months passes (maximum boundary)", () => {
    const result = loanSchema.parse({ ...validLoan, tenure_months: 600 });
    expect(result.tenure_months).toBe(600);
  });

  it("tenure of 0 fails (must be positive)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, tenure_months: 0 })
    ).toThrow();
  });

  it("negative tenure fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, tenure_months: -12 })
    ).toThrow();
  });

  it("fractional tenure fails (must be integer)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, tenure_months: 240.5 })
    ).toThrow();
  });

  it("remaining tenure of 0 fails (must be positive)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, remaining_tenure_months: 0 })
    ).toThrow();
  });

  it("remaining tenure above 600 fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, remaining_tenure_months: 601 })
    ).toThrow();
  });

  it("remaining tenure fractional fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, remaining_tenure_months: 100.7 })
    ).toThrow();
  });
});

describe("loanSchema — EMI validation", () => {
  it("zero EMI fails (must be positive)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, emi_amount: 0 })
    ).toThrow();
  });

  it("negative EMI fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, emi_amount: -5000 })
    ).toThrow();
  });

  it("very small positive EMI passes", () => {
    const result = loanSchema.parse({ ...validLoan, emi_amount: 0.01 });
    expect(result.emi_amount).toBe(0.01);
  });
});

describe("loanSchema — bank name validation", () => {
  it("bank name with max length 50 passes", () => {
    const name50 = "A".repeat(50);
    const result = loanSchema.parse({ ...validLoan, bank_name: name50 });
    expect(result.bank_name).toBe(name50);
  });

  it("bank name exceeding 50 chars fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, bank_name: "A".repeat(51) })
    ).toThrow();
  });

  it("single character bank name passes", () => {
    const result = loanSchema.parse({ ...validLoan, bank_name: "X" });
    expect(result.bank_name).toBe("X");
  });
});

describe("loanSchema — loan type validation", () => {
  const allowedTypes = [
    "home",
    "personal",
    "car",
    "education",
    "gold",
    "credit_card",
  ] as const;

  it.each(allowedTypes)("'%s' is a valid loan type", (loanType) => {
    const result = loanSchema.parse({ ...validLoan, loan_type: loanType });
    expect(result.loan_type).toBe(loanType);
  });

  it("invalid loan type fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, loan_type: "mortgage" })
    ).toThrow();
  });

  it("empty string loan type fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, loan_type: "" })
    ).toThrow();
  });

  it("numeric loan type fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, loan_type: 123 })
    ).toThrow();
  });
});

describe("loanSchema — interest rate type validation", () => {
  it.each(["floating", "fixed", "hybrid"] as const)(
    "'%s' is a valid interest rate type",
    (rateType) => {
      const result = loanSchema.parse({
        ...validLoan,
        interest_rate_type: rateType,
      });
      expect(result.interest_rate_type).toBe(rateType);
    }
  );

  it("invalid interest rate type fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, interest_rate_type: "variable" })
    ).toThrow();
  });
});

describe("loanSchema — emi_due_date boundary validation", () => {
  it("due date of 0 fails (below min 1)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, emi_due_date: 0 })
    ).toThrow();
  });

  it("due date of 1 passes (boundary)", () => {
    const result = loanSchema.parse({ ...validLoan, emi_due_date: 1 });
    expect(result.emi_due_date).toBe(1);
  });

  it("due date of 28 passes (boundary)", () => {
    const result = loanSchema.parse({ ...validLoan, emi_due_date: 28 });
    expect(result.emi_due_date).toBe(28);
  });

  it("due date of 29 fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, emi_due_date: 29 })
    ).toThrow();
  });

  it("omitting emi_due_date passes (optional field)", () => {
    const { emi_due_date, ...rest } = { ...validLoan, emi_due_date: 15 };
    const result = loanSchema.parse(rest);
    expect(result.emi_due_date).toBeUndefined();
  });

  it("fractional due date fails (must be integer)", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, emi_due_date: 15.5 })
    ).toThrow();
  });
});

describe("loanSchema — prepayment and foreclosure charges", () => {
  it("negative prepayment penalty fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, prepayment_penalty_pct: -1 })
    ).toThrow();
  });

  it("zero prepayment penalty passes", () => {
    const result = loanSchema.parse({
      ...validLoan,
      prepayment_penalty_pct: 0,
    });
    expect(result.prepayment_penalty_pct).toBe(0);
  });

  it("positive prepayment penalty passes", () => {
    const result = loanSchema.parse({
      ...validLoan,
      prepayment_penalty_pct: 2.5,
    });
    expect(result.prepayment_penalty_pct).toBe(2.5);
  });

  it("negative foreclosure charges fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, foreclosure_charges_pct: -0.5 })
    ).toThrow();
  });

  it("positive foreclosure charges passes", () => {
    const result = loanSchema.parse({
      ...validLoan,
      foreclosure_charges_pct: 3,
    });
    expect(result.foreclosure_charges_pct).toBe(3);
  });
});

describe("loanSchema — boolean eligibility fields", () => {
  it("all eligibility flags set to true", () => {
    const result = loanSchema.parse({
      ...validLoan,
      eligible_80c: true,
      eligible_24b: true,
      eligible_80e: true,
      eligible_80eea: true,
    });
    expect(result.eligible_80c).toBe(true);
    expect(result.eligible_24b).toBe(true);
    expect(result.eligible_80e).toBe(true);
    expect(result.eligible_80eea).toBe(true);
  });

  it("non-boolean eligibility value fails", () => {
    expect(() =>
      loanSchema.parse({ ...validLoan, eligible_80c: "yes" })
    ).toThrow();
  });
});

describe("loanSchema — completely empty/missing input", () => {
  it("empty object fails", () => {
    expect(() => loanSchema.parse({})).toThrow();
  });

  it("null input fails", () => {
    expect(() => loanSchema.parse(null)).toThrow();
  });

  it("undefined input fails", () => {
    expect(() => loanSchema.parse(undefined)).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Extended emiCalculatorSchema tests
// ---------------------------------------------------------------------------
describe("emiCalculatorSchema — principal validation", () => {
  it("zero principal fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 0,
        annual_rate: 8.5,
        tenure_months: 240,
      })
    ).toThrow();
  });

  it("negative principal fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: -100000,
        annual_rate: 8.5,
        tenure_months: 240,
      })
    ).toThrow();
  });

  it("very small positive principal passes", () => {
    const result = emiCalculatorSchema.parse({
      principal: 0.01,
      annual_rate: 8.5,
      tenure_months: 240,
    });
    expect(result.principal).toBe(0.01);
  });
});

describe("emiCalculatorSchema — annual rate validation", () => {
  it("zero annual rate passes (boundary)", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 0,
      tenure_months: 240,
    });
    expect(result.annual_rate).toBe(0);
  });

  it("negative annual rate fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: -1,
        tenure_months: 240,
      })
    ).toThrow();
  });

  it("exact 50% passes (boundary)", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 50,
      tenure_months: 240,
    });
    expect(result.annual_rate).toBe(50);
  });

  it("above 50% fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: 50.1,
        tenure_months: 240,
      })
    ).toThrow();
  });
});

describe("emiCalculatorSchema — tenure validation", () => {
  it("tenure of 1 month passes (boundary)", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 8.5,
      tenure_months: 1,
    });
    expect(result.tenure_months).toBe(1);
  });

  it("tenure of 600 months passes (boundary)", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 8.5,
      tenure_months: 600,
    });
    expect(result.tenure_months).toBe(600);
  });

  it("tenure of 0 fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: 8.5,
        tenure_months: 0,
      })
    ).toThrow();
  });

  it("tenure above 600 fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: 8.5,
        tenure_months: 601,
      })
    ).toThrow();
  });

  it("negative tenure fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: 8.5,
        tenure_months: -10,
      })
    ).toThrow();
  });

  it("fractional tenure fails (must be integer)", () => {
    expect(() =>
      emiCalculatorSchema.parse({
        principal: 5000000,
        annual_rate: 8.5,
        tenure_months: 120.5,
      })
    ).toThrow();
  });
});

describe("emiCalculatorSchema — monthly prepayment validation", () => {
  it("zero prepayment passes", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 8.5,
      tenure_months: 240,
      monthly_prepayment: 0,
    });
    expect(result.monthly_prepayment).toBe(0);
  });

  it("positive prepayment passes", () => {
    const result = emiCalculatorSchema.parse({
      principal: 5000000,
      annual_rate: 8.5,
      tenure_months: 240,
      monthly_prepayment: 10000,
    });
    expect(result.monthly_prepayment).toBe(10000);
  });
});

describe("emiCalculatorSchema — missing required fields", () => {
  it("missing principal fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({ annual_rate: 8.5, tenure_months: 240 })
    ).toThrow();
  });

  it("missing annual_rate fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({ principal: 5000000, tenure_months: 240 })
    ).toThrow();
  });

  it("missing tenure_months fails", () => {
    expect(() =>
      emiCalculatorSchema.parse({ principal: 5000000, annual_rate: 8.5 })
    ).toThrow();
  });

  it("empty object fails", () => {
    expect(() => emiCalculatorSchema.parse({})).toThrow();
  });
});
