import { describe, expect, test } from "vitest";
import { formatAXN, axnToUSD } from "../format";

// ---------------------------------------------------------------------------
// formatAXN
// ---------------------------------------------------------------------------

describe("formatAXN", () => {
  test("zero", () => {
    expect(formatAXN(0)).toBe("0.00 AXN");
  });

  test("small amount 123.45", () => {
    expect(formatAXN(123.45)).toBe("123.45 AXN");
  });

  test("exactly 999", () => {
    expect(formatAXN(999)).toBe("999.00 AXN");
  });

  test("thousands 5000", () => {
    expect(formatAXN(5000)).toBe("5.0K AXN");
  });

  test("exactly 1000", () => {
    expect(formatAXN(1000)).toBe("1.0K AXN");
  });

  test("millions 2500000", () => {
    expect(formatAXN(2500000)).toBe("2.50M AXN");
  });

  test("exactly 1000000", () => {
    expect(formatAXN(1000000)).toBe("1.00M AXN");
  });

  test("fractional 0.01", () => {
    expect(formatAXN(0.01)).toBe("0.01 AXN");
  });
});

// ---------------------------------------------------------------------------
// axnToUSD
// ---------------------------------------------------------------------------

describe("axnToUSD", () => {
  test("1000 AXN default rate", () => {
    // 1000 * 0.001 = $1.00
    expect(axnToUSD(1000)).toBe("$1.00");
  });

  test("zero", () => {
    expect(axnToUSD(0)).toBe("$0.00");
  });

  test("custom rate 100 at 0.01", () => {
    // 100 * 0.01 = $1.00
    expect(axnToUSD(100, 0.01)).toBe("$1.00");
  });

  test("1000000 AXN", () => {
    // 1000000 * 0.001 = $1000.00
    expect(axnToUSD(1000000)).toBe("$1000.00");
  });

  test("1 AXN rounds to $0.00", () => {
    // 1 * 0.001 = $0.001 → rounds to $0.00
    expect(axnToUSD(1)).toBe("$0.00");
  });

  test("500 AXN", () => {
    // 500 * 0.001 = $0.50
    expect(axnToUSD(500)).toBe("$0.50");
  });
});
