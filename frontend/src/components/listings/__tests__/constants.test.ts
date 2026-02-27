import { describe, it, expect } from "vitest";
import {
  CATEGORY_ICONS,
  CATEGORY_ACCENT,
  CATEGORY_GLOW,
} from "../constants";

// ── CATEGORY_ICONS ──────────────────────────────────────────────────────────

describe("CATEGORY_ICONS", () => {
  const EXPECTED_CATEGORIES = [
    "web_search",
    "code_analysis",
    "document_summary",
    "api_response",
    "computation",
  ] as const;

  it("exports an object with exactly 5 category keys", () => {
    expect(Object.keys(CATEGORY_ICONS)).toHaveLength(5);
  });

  it("contains all expected category keys", () => {
    for (const key of EXPECTED_CATEGORIES) {
      expect(CATEGORY_ICONS).toHaveProperty(key);
    }
  });

  it("maps each category to a renderable value", () => {
    for (const key of EXPECTED_CATEGORIES) {
      // Lucide icons are ForwardRef components; they are objects with a $$typeof symbol or functions
      const icon = CATEGORY_ICONS[key];
      expect(icon).toBeTruthy();
    }
  });

  it("maps web_search to the Search icon", () => {
    const icon = CATEGORY_ICONS["web_search"];
    expect(icon).toBeTruthy();
    // Lucide React icons expose a displayName
    expect(icon.displayName).toBe("Search");
  });

  it("maps code_analysis to the Code icon", () => {
    const icon = CATEGORY_ICONS["code_analysis"];
    expect(icon).toBeTruthy();
    expect(icon.displayName).toBe("Code");
  });

  it("maps document_summary to the FileText icon", () => {
    const icon = CATEGORY_ICONS["document_summary"];
    expect(icon).toBeTruthy();
    expect(icon.displayName).toBe("FileText");
  });

  it("maps api_response to the Globe icon", () => {
    const icon = CATEGORY_ICONS["api_response"];
    expect(icon).toBeTruthy();
    expect(icon.displayName).toBe("Globe");
  });

  it("maps computation to the Cpu icon", () => {
    const icon = CATEGORY_ICONS["computation"];
    expect(icon).toBeTruthy();
    expect(icon.displayName).toBe("Cpu");
  });

  it("does not contain any extra unexpected keys", () => {
    const keys = Object.keys(CATEGORY_ICONS);
    for (const key of keys) {
      expect(EXPECTED_CATEGORIES as readonly string[]).toContain(key);
    }
  });
});

// ── CATEGORY_ACCENT ──────────────────────────────────────────────────────────

describe("CATEGORY_ACCENT", () => {
  it("exports an object with exactly 5 category keys", () => {
    expect(Object.keys(CATEGORY_ACCENT)).toHaveLength(5);
  });

  it("maps web_search to the blue accent color", () => {
    expect(CATEGORY_ACCENT["web_search"]).toBe("#60a5fa");
  });

  it("maps code_analysis to the purple accent color", () => {
    expect(CATEGORY_ACCENT["code_analysis"]).toBe("#a78bfa");
  });

  it("maps document_summary to the green accent color", () => {
    expect(CATEGORY_ACCENT["document_summary"]).toBe("#34d399");
  });

  it("maps api_response to the amber accent color", () => {
    expect(CATEGORY_ACCENT["api_response"]).toBe("#fbbf24");
  });

  it("maps computation to the cyan accent color", () => {
    expect(CATEGORY_ACCENT["computation"]).toBe("#22d3ee");
  });

  it("all values are valid hex color strings", () => {
    for (const value of Object.values(CATEGORY_ACCENT)) {
      expect(value).toMatch(/^#[0-9a-f]{6}$/i);
    }
  });

  it("has no duplicate accent colors", () => {
    const values = Object.values(CATEGORY_ACCENT);
    const uniqueValues = new Set(values);
    expect(uniqueValues.size).toBe(values.length);
  });
});

// ── CATEGORY_GLOW ──────────────────────────────────────────────────────────

describe("CATEGORY_GLOW", () => {
  it("exports an object with exactly 5 category keys", () => {
    expect(Object.keys(CATEGORY_GLOW)).toHaveLength(5);
  });

  it("maps web_search to the blue glow value", () => {
    expect(CATEGORY_GLOW["web_search"]).toBe("rgba(96,165,250,0.25)");
  });

  it("maps code_analysis to the purple glow value", () => {
    expect(CATEGORY_GLOW["code_analysis"]).toBe("rgba(167,139,250,0.25)");
  });

  it("maps document_summary to the green glow value", () => {
    expect(CATEGORY_GLOW["document_summary"]).toBe("rgba(52,211,153,0.25)");
  });

  it("maps api_response to the amber glow value", () => {
    expect(CATEGORY_GLOW["api_response"]).toBe("rgba(251,191,36,0.25)");
  });

  it("maps computation to the cyan glow value", () => {
    expect(CATEGORY_GLOW["computation"]).toBe("rgba(34,211,238,0.25)");
  });

  it("all values are valid rgba color strings", () => {
    for (const value of Object.values(CATEGORY_GLOW)) {
      expect(value).toMatch(/^rgba\(\d+,\d+,\d+,[\d.]+\)$/);
    }
  });

  it("all glow values use 0.25 alpha", () => {
    for (const value of Object.values(CATEGORY_GLOW)) {
      expect(value).toContain("0.25)");
    }
  });

  it("has matching keys with CATEGORY_ACCENT and CATEGORY_ICONS", () => {
    const glowKeys = Object.keys(CATEGORY_GLOW).sort();
    const accentKeys = Object.keys(CATEGORY_ACCENT).sort();
    const iconKeys = Object.keys(CATEGORY_ICONS).sort();
    expect(glowKeys).toEqual(accentKeys);
    expect(glowKeys).toEqual(iconKeys);
  });
});
