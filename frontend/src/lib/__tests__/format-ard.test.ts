import { describe, expect, test } from "vitest";
import { formatARD, ardToUSD } from "../format";

// ---------------------------------------------------------------------------
// formatARD
// ---------------------------------------------------------------------------

describe("formatARD", () => {
  test("zero", () => {
    expect(formatARD(0)).toBe("0.00 ARD");
  });

  test("small amount 123.45", () => {
    expect(formatARD(123.45)).toBe("123.45 ARD");
  });

  test("exactly 999", () => {
    expect(formatARD(999)).toBe("999.00 ARD");
  });

  test("thousands 5000", () => {
    expect(formatARD(5000)).toBe("5.0K ARD");
  });

  test("exactly 1000", () => {
    expect(formatARD(1000)).toBe("1.0K ARD");
  });

  test("millions 2500000", () => {
    expect(formatARD(2500000)).toBe("2.50M ARD");
  });

  test("exactly 1000000", () => {
    expect(formatARD(1000000)).toBe("1.00M ARD");
  });

  test("fractional 0.01", () => {
    expect(formatARD(0.01)).toBe("0.01 ARD");
  });
});

// ---------------------------------------------------------------------------
// ardToUSD
// ---------------------------------------------------------------------------

describe("ardToUSD", () => {
  test("1000 ARD default rate", () => {
    // 1000 * 0.001 = $1.00
    expect(ardToUSD(1000)).toBe("$1.00");
  });

  test("zero", () => {
    expect(ardToUSD(0)).toBe("$0.00");
  });

  test("custom rate 100 at 0.01", () => {
    // 100 * 0.01 = $1.00
    expect(ardToUSD(100, 0.01)).toBe("$1.00");
  });

  test("1000000 ARD", () => {
    // 1000000 * 0.001 = $1000.00
    expect(ardToUSD(1000000)).toBe("$1000.00");
  });

  test("1 ARD rounds to $0.00", () => {
    // 1 * 0.001 = $0.001 → rounds to $0.00
    expect(ardToUSD(1)).toBe("$0.00");
  });

  test("500 ARD", () => {
    // 500 * 0.001 = $0.50
    expect(ardToUSD(500)).toBe("$0.50");
  });
});
