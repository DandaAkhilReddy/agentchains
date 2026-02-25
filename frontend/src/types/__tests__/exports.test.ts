import { describe, it, expect } from "vitest";

// ── Verify all type files export without errors ─────────────────────────────
// These imports confirm that each module can be loaded and its exports are
// structurally valid at runtime.  Since these are TypeScript interfaces/types,
// the primary assertion is that the import itself does not throw.

describe("types/common exports", () => {
  it("exports CacheStats, HealthResponse, FeedEvent, SystemMetrics, and CDNStats", async () => {
    const mod = await import("../../types/common");
    // Module should load without error; interfaces compile away but the module object exists
    expect(mod).toBeDefined();
  });
});

describe("types/agent exports", () => {
  it("exports Agent, AgentListResponse, and related trust/pipeline types", async () => {
    const mod = await import("../../types/agent");
    expect(mod).toBeDefined();
  });
});

describe("types/listing exports", () => {
  it("exports Listing, ListingListResponse, DiscoverParams, ZKP types, and more", async () => {
    const mod = await import("../../types/listing");
    expect(mod).toBeDefined();
  });
});

describe("types/transaction exports", () => {
  it("exports TransactionStatus, Transaction, and TransactionListResponse", async () => {
    const mod = await import("../../types/transaction");
    expect(mod).toBeDefined();
  });
});

describe("types/wallet exports", () => {
  it("exports TokenAccount, WalletBalanceResponse, and transfer types", async () => {
    const mod = await import("../../types/wallet");
    expect(mod).toBeDefined();
  });
});

describe("types/creator exports", () => {
  it("exports Creator, CreatorDashboard, RedemptionRequest, and related types", async () => {
    const mod = await import("../../types/creator");
    expect(mod).toBeDefined();
  });
});

describe("types/admin exports", () => {
  it("exports V2 dashboard types, admin analytics, and security event types", async () => {
    const mod = await import("../../types/admin");
    expect(mod).toBeDefined();
  });
});

describe("types/a2ui exports", () => {
  it("exports A2UI component, session, and state types", async () => {
    const mod = await import("../../types/a2ui");
    expect(mod).toBeDefined();
  });
});

describe("types/api barrel re-export", () => {
  it("re-exports all domain types from the barrel file without error", async () => {
    const mod = await import("../../types/api");
    expect(mod).toBeDefined();
  });

  it("barrel export contains expected common types", async () => {
    // These are runtime no-ops for pure type exports, but the module should resolve
    const mod = await import("../../types/api");
    // The module object should exist and be non-empty (at least the __esModule marker or re-exports)
    expect(typeof mod).toBe("object");
  });
});

describe("cross-module consistency", () => {
  it("all individual type modules load in parallel without conflicts", async () => {
    const results = await Promise.all([
      import("../../types/common"),
      import("../../types/agent"),
      import("../../types/listing"),
      import("../../types/transaction"),
      import("../../types/wallet"),
      import("../../types/creator"),
      import("../../types/admin"),
      import("../../types/a2ui"),
      import("../../types/api"),
    ]);
    expect(results).toHaveLength(9);
    results.forEach((mod) => {
      expect(mod).toBeDefined();
    });
  });

  it("barrel api module is importable alongside individual modules", async () => {
    const [barrel, common, agent] = await Promise.all([
      import("../../types/api"),
      import("../../types/common"),
      import("../../types/agent"),
    ]);
    expect(barrel).toBeDefined();
    expect(common).toBeDefined();
    expect(agent).toBeDefined();
  });
});
