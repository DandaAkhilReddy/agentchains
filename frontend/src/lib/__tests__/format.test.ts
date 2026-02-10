import { describe, it, expect } from "vitest";
import {
  formatINR,
  formatINRCompact,
  formatUSD,
  formatUSDCompact,
  formatCurrency,
  formatCurrencyCompact,
  formatPercent,
  formatMonths,
  formatDate,
} from "../format";

describe("formatINR", () => {
  it("formats zero", () => {
    expect(formatINR(0)).toBe("₹0");
  });

  it("formats small amounts without Indian grouping", () => {
    expect(formatINR(500)).toBe("₹500");
  });

  it("formats amounts with Indian grouping (last 3, then groups of 2)", () => {
    expect(formatINR(100000)).toBe("₹1,00,000");
  });

  it("formats 50 lakhs correctly", () => {
    expect(formatINR(5000000)).toBe("₹50,00,000");
  });

  it("formats 1 crore correctly", () => {
    expect(formatINR(10000000)).toBe("₹1,00,00,000");
  });

  it("formats with paisa (decimal)", () => {
    expect(formatINR(43391.50)).toBe("₹43,391.50");
  });

  it("strips trailing .00", () => {
    expect(formatINR(43391.00)).toBe("₹43,391");
  });

  it("formats negative amounts", () => {
    expect(formatINR(-5000)).toBe("-₹5,000");
  });
});

describe("formatINRCompact", () => {
  it("formats crores", () => {
    expect(formatINRCompact(10000000)).toBe("₹1.0Cr");
  });

  it("formats lakhs", () => {
    expect(formatINRCompact(500000)).toBe("₹5.0L");
  });

  it("formats thousands", () => {
    expect(formatINRCompact(5000)).toBe("₹5.0K");
  });

  it("falls back to formatINR for small amounts", () => {
    expect(formatINRCompact(500)).toBe("₹500");
  });
});

describe("formatPercent", () => {
  it("formats percentage with 2 decimals", () => {
    expect(formatPercent(8.5)).toBe("8.50%");
  });

  it("formats zero percent", () => {
    expect(formatPercent(0)).toBe("0.00%");
  });
});

describe("formatMonths", () => {
  it("formats months only", () => {
    expect(formatMonths(6)).toBe("6 months");
  });

  it("formats 1 month (singular)", () => {
    expect(formatMonths(1)).toBe("1 month");
  });

  it("formats years only", () => {
    expect(formatMonths(24)).toBe("2 years");
  });

  it("formats 1 year (singular)", () => {
    expect(formatMonths(12)).toBe("1 year");
  });

  it("formats mixed years and months", () => {
    expect(formatMonths(30)).toBe("2y 6m");
  });
});

describe("formatDate", () => {
  it("formats a date string", () => {
    const result = formatDate("2025-01-15");
    expect(result).toContain("Jan");
    expect(result).toContain("2025");
  });

  it("formats a date with IN locale (default)", () => {
    const result = formatDate("2025-07-04", "IN");
    expect(result).toContain("Jul");
    expect(result).toContain("2025");
  });

  it("formats a date with US locale", () => {
    const result = formatDate("2025-07-04", "US");
    expect(result).toContain("Jul");
    expect(result).toContain("2025");
  });
});

// ---------- USD formatting ----------

describe("formatUSD", () => {
  it("formats a basic amount with commas and cents", () => {
    expect(formatUSD(1234.56)).toBe("$1,234.56");
  });

  it("formats zero", () => {
    expect(formatUSD(0)).toBe("$0");
  });

  it("formats negative amounts", () => {
    expect(formatUSD(-5000)).toBe("-$5,000");
  });

  it("strips trailing .00 decimals", () => {
    expect(formatUSD(2500.0)).toBe("$2,500");
  });

  it("formats large amounts (1 million)", () => {
    expect(formatUSD(1000000)).toBe("$1,000,000");
  });

  it("formats large amounts (10 million)", () => {
    expect(formatUSD(10000000)).toBe("$10,000,000");
  });

  it("preserves non-zero cents", () => {
    expect(formatUSD(99.99)).toBe("$99.99");
  });

  it("formats small amounts without commas", () => {
    expect(formatUSD(42)).toBe("$42");
  });
});

describe("formatUSDCompact", () => {
  it("formats billions with B suffix", () => {
    expect(formatUSDCompact(2500000000)).toBe("$2.5B");
  });

  it("formats millions with M suffix", () => {
    expect(formatUSDCompact(1500000)).toBe("$1.5M");
  });

  it("formats exact million", () => {
    expect(formatUSDCompact(1000000)).toBe("$1.0M");
  });

  it("formats thousands with K suffix", () => {
    expect(formatUSDCompact(5000)).toBe("$5.0K");
  });

  it("formats exact thousand", () => {
    expect(formatUSDCompact(1000)).toBe("$1.0K");
  });

  it("falls back to formatUSD for small amounts", () => {
    expect(formatUSDCompact(500)).toBe("$500");
  });
});

// ---------- Country-aware formatting ----------

describe("formatCurrency", () => {
  it("returns INR format for IN country (default)", () => {
    expect(formatCurrency(100000)).toBe("₹1,00,000");
  });

  it("returns INR format when country is explicitly IN", () => {
    expect(formatCurrency(100000, "IN")).toBe("₹1,00,000");
  });

  it("returns USD format for US country", () => {
    expect(formatCurrency(100000, "US")).toBe("$100,000");
  });

  it("handles zero for both countries", () => {
    expect(formatCurrency(0, "IN")).toBe("₹0");
    expect(formatCurrency(0, "US")).toBe("$0");
  });
});

describe("formatCurrencyCompact", () => {
  it("uses INR compact for IN country (lakhs)", () => {
    expect(formatCurrencyCompact(500000, "IN")).toBe("₹5.0L");
  });

  it("uses INR compact for IN country (crores)", () => {
    expect(formatCurrencyCompact(10000000, "IN")).toBe("₹1.0Cr");
  });

  it("uses USD compact for US country (millions)", () => {
    expect(formatCurrencyCompact(1000000, "US")).toBe("$1.0M");
  });

  it("uses USD compact for US country (thousands)", () => {
    expect(formatCurrencyCompact(5000, "US")).toBe("$5.0K");
  });

  it("defaults to IN when country is omitted", () => {
    expect(formatCurrencyCompact(500000)).toBe("₹5.0L");
  });
});

// ---------- Additional shared utility coverage ----------

describe("formatMonths (additional)", () => {
  it("formats 0 months", () => {
    expect(formatMonths(0)).toBe("0 months");
  });

  it("formats large month count as years+months", () => {
    expect(formatMonths(100)).toBe("8y 4m");
  });

  it("formats exactly 5 years", () => {
    expect(formatMonths(60)).toBe("5 years");
  });

  it("formats 13 months as years+months", () => {
    expect(formatMonths(13)).toBe("1y 1m");
  });
});

describe("formatPercent (additional)", () => {
  it("formats whole number with trailing zeros", () => {
    expect(formatPercent(10)).toBe("10.00%");
  });

  it("formats small decimal percentages", () => {
    expect(formatPercent(0.5)).toBe("0.50%");
  });

  it("formats large percentages", () => {
    expect(formatPercent(100)).toBe("100.00%");
  });

  it("formats negative percentages", () => {
    expect(formatPercent(-2.5)).toBe("-2.50%");
  });

  it("formats percentages with many decimals (truncates to 2)", () => {
    expect(formatPercent(8.999)).toBe("9.00%");
  });
});
