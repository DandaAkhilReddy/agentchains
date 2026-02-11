import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import {
  relativeTime,
  formatUSDC,
  truncateId,
  formatBytes,
  scoreToPercent,
} from "../format";

describe("relativeTime", () => {
  beforeEach(() => {
    // Mock Date.now() to return a fixed timestamp for consistent testing
    vi.spyOn(Date, "now").mockReturnValue(1704067200000); // 2024-01-01 00:00:00 UTC
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("returns '—' for null input", () => {
    expect(relativeTime(null)).toBe("—");
  });

  test("returns 'just now' for time less than 60 seconds ago", () => {
    // 30 seconds ago
    const thirtySecondsAgo = new Date(1704067200000 - 30 * 1000).toISOString();
    expect(relativeTime(thirtySecondsAgo)).toBe("just now");
  });

  test("returns 'just now' for time 0 seconds ago", () => {
    const now = new Date(1704067200000).toISOString();
    expect(relativeTime(now)).toBe("just now");
  });

  test("returns minutes for time less than 60 minutes ago", () => {
    // 5 minutes ago
    const fiveMinutesAgo = new Date(1704067200000 - 5 * 60 * 1000).toISOString();
    expect(relativeTime(fiveMinutesAgo)).toBe("5m ago");
  });

  test("returns minutes for time at 59 minutes ago", () => {
    // 59 minutes ago
    const fiftyNineMinutesAgo = new Date(1704067200000 - 59 * 60 * 1000).toISOString();
    expect(relativeTime(fiftyNineMinutesAgo)).toBe("59m ago");
  });

  test("returns hours for time less than 24 hours ago", () => {
    // 3 hours ago
    const threeHoursAgo = new Date(1704067200000 - 3 * 60 * 60 * 1000).toISOString();
    expect(relativeTime(threeHoursAgo)).toBe("3h ago");
  });

  test("returns hours for time at 23 hours ago", () => {
    // 23 hours ago
    const twentyThreeHoursAgo = new Date(1704067200000 - 23 * 60 * 60 * 1000).toISOString();
    expect(relativeTime(twentyThreeHoursAgo)).toBe("23h ago");
  });

  test("returns days for time 24 hours or more ago", () => {
    // 2 days ago
    const twoDaysAgo = new Date(1704067200000 - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(relativeTime(twoDaysAgo)).toBe("2d ago");
  });

  test("returns days for time 30 days ago", () => {
    // 30 days ago
    const thirtyDaysAgo = new Date(1704067200000 - 30 * 24 * 60 * 60 * 1000).toISOString();
    expect(relativeTime(thirtyDaysAgo)).toBe("30d ago");
  });
});

describe("formatUSDC", () => {
  test("formats very small amounts with 6 decimals", () => {
    expect(formatUSDC(0.001234)).toBe("$0.001234");
  });

  test("formats amounts less than 0.01 with 6 decimals", () => {
    expect(formatUSDC(0.009999)).toBe("$0.009999");
  });

  test("formats normal amounts with 4 decimals", () => {
    expect(formatUSDC(1.2345678)).toBe("$1.2346");
  });

  test("formats amounts at 0.01 threshold with 4 decimals", () => {
    expect(formatUSDC(0.01)).toBe("$0.0100");
  });

  test("formats zero with 6 decimals", () => {
    expect(formatUSDC(0)).toBe("$0.000000");
  });

  test("formats large amounts with 4 decimals", () => {
    expect(formatUSDC(12345.6789)).toBe("$12345.6789");
  });
});

describe("truncateId", () => {
  test("returns short ID unchanged", () => {
    expect(truncateId("abc123")).toBe("abc123");
  });

  test("truncates long ID with default length", () => {
    expect(truncateId("abcdefghijklmnop")).toBe("abcdefgh...");
  });

  test("truncates long ID with custom length", () => {
    expect(truncateId("abcdefghijklmnop", 4)).toBe("abcd...");
  });

  test("returns ID unchanged when exactly at default length", () => {
    expect(truncateId("12345678")).toBe("12345678");
  });

  test("returns empty string for empty input", () => {
    expect(truncateId("")).toBe("");
  });

  test("truncates very long ID correctly", () => {
    expect(truncateId("0x1234567890abcdef1234567890abcdef", 12)).toBe("0x1234567890...");
  });
});

describe("formatBytes", () => {
  test("formats bytes less than 1024", () => {
    expect(formatBytes(512)).toBe("512 B");
  });

  test("formats zero bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  test("formats KB range with 1 decimal", () => {
    expect(formatBytes(2048)).toBe("2.0 KB");
  });

  test("formats KB with decimals", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
  });

  test("formats MB range with 1 decimal", () => {
    expect(formatBytes(2097152)).toBe("2.0 MB");
  });

  test("formats MB with decimals", () => {
    expect(formatBytes(1572864)).toBe("1.5 MB");
  });

  test("formats large MB amounts", () => {
    expect(formatBytes(52428800)).toBe("50.0 MB");
  });
});

describe("scoreToPercent", () => {
  test("formats zero score", () => {
    expect(scoreToPercent(0)).toBe("0%");
  });

  test("formats perfect score", () => {
    expect(scoreToPercent(1)).toBe("100%");
  });

  test("formats decimal score with rounding", () => {
    expect(scoreToPercent(0.847)).toBe("85%");
  });

  test("formats low score", () => {
    expect(scoreToPercent(0.123)).toBe("12%");
  });

  test("formats high score", () => {
    expect(scoreToPercent(0.999)).toBe("100%");
  });

  test("formats score with rounding down", () => {
    expect(scoreToPercent(0.844)).toBe("84%");
  });

  test("formats score with rounding up", () => {
    expect(scoreToPercent(0.845)).toBe("85%");
  });
});
