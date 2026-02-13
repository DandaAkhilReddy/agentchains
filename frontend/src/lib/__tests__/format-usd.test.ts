import { describe, expect, test } from "vitest";
import { formatUSD } from "../format";

// ---------------------------------------------------------------------------
// formatUSD
// ---------------------------------------------------------------------------

describe("formatUSD", () => {
  test("zero", () => {
    expect(formatUSD(0)).toBe("$0.00");
  });

  test("small amount 1.50", () => {
    expect(formatUSD(1.5)).toBe("$1.50");
  });

  test("sub-dollar 0.99", () => {
    expect(formatUSD(0.99)).toBe("$0.99");
  });

  test("thousands 1234.56", () => {
    expect(formatUSD(1234.56)).toBe("$1.2K");
  });

  test("exactly 1000", () => {
    expect(formatUSD(1000)).toBe("$1.0K");
  });

  test("millions 1500000", () => {
    expect(formatUSD(1_500_000)).toBe("$1.5M");
  });

  test("exactly 1000000", () => {
    expect(formatUSD(1_000_000)).toBe("$1.0M");
  });

  test("small fractional 0.01", () => {
    expect(formatUSD(0.01)).toBe("$0.01");
  });

  test("round hundreds 500", () => {
    expect(formatUSD(500)).toBe("$500.00");
  });

  test("large millions 25000000", () => {
    expect(formatUSD(25_000_000)).toBe("$25.0M");
  });
});
