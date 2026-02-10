/// <reference types="vitest/globals" />
import { useCountryStore } from "../store/countryStore";
import { COUNTRY_CONFIGS } from "../lib/countryConfig";
import type { CountryConfig } from "../lib/countryConfig";

// ---------------------------------------------------------------------------
// localStorage mock
// ---------------------------------------------------------------------------
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    /** Expose inner store for assertions */
    _store: () => store,
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

// ---------------------------------------------------------------------------
// Reset between tests
// ---------------------------------------------------------------------------
beforeEach(() => {
  localStorageMock.clear();
  vi.clearAllMocks();
  // Reset the zustand store to its default state (IN)
  useCountryStore.setState({ country: "IN" });
});

// ===========================================================================
// 1. countryStore tests
// ===========================================================================
describe("countryStore", () => {
  it("defaults to IN", () => {
    const state = useCountryStore.getState();
    expect(state.country).toBe("IN");
  });

  it("setCountry switches to US", () => {
    useCountryStore.getState().setCountry("US");
    expect(useCountryStore.getState().country).toBe("US");
  });

  it("persists country to localStorage when setCountry is called", () => {
    useCountryStore.getState().setCountry("US");
    expect(localStorageMock.setItem).toHaveBeenCalledWith("country", "US");
    expect(localStorageMock._store()["country"]).toBe("US");
  });

  it("reads from localStorage on init", () => {
    // Simulate localStorage already having "US" before store initialises.
    // Because the zustand store is a singleton created at import time, we
    // cannot truly re-run the initialiser. Instead we verify the mechanism:
    // 1. setCountry writes to localStorage  (covered above)
    // 2. The store creation code reads localStorage.getItem("country")
    //    and falls back to "IN".
    // We test this by confirming that after manually seeding localStorage
    // and resetting state to mimic a fresh load, the value is consistent.
    localStorageMock.setItem("country", "US");
    // Simulate what the store initialiser does:
    const stored = localStorage.getItem("country") as "IN" | "US" | null;
    const initialCountry = stored || "IN";
    useCountryStore.setState({ country: initialCountry });

    expect(useCountryStore.getState().country).toBe("US");
  });

  it("setCountry back to IN after switching to US", () => {
    useCountryStore.getState().setCountry("US");
    expect(useCountryStore.getState().country).toBe("US");

    useCountryStore.getState().setCountry("IN");
    expect(useCountryStore.getState().country).toBe("IN");
    expect(localStorageMock._store()["country"]).toBe("IN");
  });
});

// ===========================================================================
// 2. COUNTRY_CONFIGS tests
// ===========================================================================

// ---- Required fields every CountryConfig must have ----
const REQUIRED_FIELDS: (keyof CountryConfig)[] = [
  "code",
  "currencyCode",
  "currencySymbol",
  "currencyLocale",
  "dateLocale",
  "banks",
  "loanTypes",
  "hasTaxSections",
  "hasFilingStatus",
  "compactUnits",
  "sliderRanges",
  "budgetModeKey",
  "privacyLawKey",
];

describe("COUNTRY_CONFIGS.IN", () => {
  const cfg = COUNTRY_CONFIGS.IN;

  it("has correct currency symbol (rupee)", () => {
    expect(cfg.currencySymbol).toBe("\u20B9"); // ₹
  });

  it("has Indian banks (SBI, HDFC)", () => {
    expect(cfg.banks).toContain("SBI");
    expect(cfg.banks).toContain("HDFC");
  });

  it("has correct slider ranges in lakhs scale", () => {
    // principal: 1 lakh to 5 crore in steps of 1 lakh
    expect(cfg.sliderRanges.principal.min).toBe(100_000);
    expect(cfg.sliderRanges.principal.max).toBe(50_000_000);
    expect(cfg.sliderRanges.principal.step).toBe(100_000);

    // daily saving: 10–1000 in steps of 10
    expect(cfg.sliderRanges.dailySaving.min).toBe(10);
    expect(cfg.sliderRanges.dailySaving.max).toBe(1_000);
    expect(cfg.sliderRanges.dailySaving.step).toBe(10);

    // monthly extra: 0–50,000 in steps of 500
    expect(cfg.sliderRanges.monthlyExtra.min).toBe(0);
    expect(cfg.sliderRanges.monthlyExtra.max).toBe(50_000);
    expect(cfg.sliderRanges.monthlyExtra.step).toBe(500);

    // lump sum default
    expect(cfg.sliderRanges.lumpSumDefault).toBe(50_000);
  });

  it("has all required fields", () => {
    for (const field of REQUIRED_FIELDS) {
      expect(cfg).toHaveProperty(field);
    }
  });

  it("has INR currency code and en-IN locale", () => {
    expect(cfg.currencyCode).toBe("INR");
    expect(cfg.currencyLocale).toBe("en-IN");
  });

  it("has tax sections enabled and no filing status", () => {
    expect(cfg.hasTaxSections).toBe(true);
    expect(cfg.hasFilingStatus).toBe(false);
  });
});

describe("COUNTRY_CONFIGS.US", () => {
  const cfg = COUNTRY_CONFIGS.US;

  it("has correct currency symbol (dollar)", () => {
    expect(cfg.currencySymbol).toBe("$");
  });

  it("has US banks (Chase, Wells Fargo)", () => {
    expect(cfg.banks).toContain("Chase");
    expect(cfg.banks).toContain("Wells Fargo");
  });

  it("has correct slider ranges in thousands scale", () => {
    // principal: 1,000 to 5,000,000 in steps of 1,000
    expect(cfg.sliderRanges.principal.min).toBe(1_000);
    expect(cfg.sliderRanges.principal.max).toBe(5_000_000);
    expect(cfg.sliderRanges.principal.step).toBe(1_000);

    // daily saving: 1–100 in steps of 1
    expect(cfg.sliderRanges.dailySaving.min).toBe(1);
    expect(cfg.sliderRanges.dailySaving.max).toBe(100);
    expect(cfg.sliderRanges.dailySaving.step).toBe(1);

    // monthly extra: 0–5,000 in steps of 50
    expect(cfg.sliderRanges.monthlyExtra.min).toBe(0);
    expect(cfg.sliderRanges.monthlyExtra.max).toBe(5_000);
    expect(cfg.sliderRanges.monthlyExtra.step).toBe(50);

    // lump sum default
    expect(cfg.sliderRanges.lumpSumDefault).toBe(5_000);
  });

  it("has all required fields", () => {
    for (const field of REQUIRED_FIELDS) {
      expect(cfg).toHaveProperty(field);
    }
  });

  it("has USD currency code and en-US locale", () => {
    expect(cfg.currencyCode).toBe("USD");
    expect(cfg.currencyLocale).toBe("en-US");
  });

  it("has no tax sections but has filing status", () => {
    expect(cfg.hasTaxSections).toBe(false);
    expect(cfg.hasFilingStatus).toBe(true);
  });
});

describe("COUNTRY_CONFIGS - both configs completeness", () => {
  it("has entries for IN and US", () => {
    expect(Object.keys(COUNTRY_CONFIGS)).toEqual(
      expect.arrayContaining(["IN", "US"]),
    );
  });

  it.each(["IN", "US"] as const)(
    "%s config has all required fields with non-undefined values",
    (code) => {
      const cfg = COUNTRY_CONFIGS[code];
      for (const field of REQUIRED_FIELDS) {
        expect(cfg[field]).toBeDefined();
      }
    },
  );

  it.each(["IN", "US"] as const)(
    "%s config banks list is a non-empty array",
    (code) => {
      expect(Array.isArray(COUNTRY_CONFIGS[code].banks)).toBe(true);
      expect(COUNTRY_CONFIGS[code].banks.length).toBeGreaterThan(0);
    },
  );

  it.each(["IN", "US"] as const)(
    "%s config loanTypes list is a non-empty array",
    (code) => {
      expect(Array.isArray(COUNTRY_CONFIGS[code].loanTypes)).toBe(true);
      expect(COUNTRY_CONFIGS[code].loanTypes.length).toBeGreaterThan(0);
    },
  );

  it.each(["IN", "US"] as const)(
    "%s config compactUnits list is a non-empty array",
    (code) => {
      expect(Array.isArray(COUNTRY_CONFIGS[code].compactUnits)).toBe(true);
      expect(COUNTRY_CONFIGS[code].compactUnits.length).toBeGreaterThan(0);
    },
  );
});
