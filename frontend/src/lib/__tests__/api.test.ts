import { describe, expect, test, vi, beforeEach } from "vitest";
import {
  fetchHealth,
  fetchAgents,
  fetchListings,
  fetchDiscover,
  fetchTransactions,
  fetchLeaderboard,
  fetchReputation,
  expressBuy,
  autoMatch,
  fetchTrending,
  fetchDemandGaps,
  fetchOpportunities,
  fetchMyEarnings,
  fetchMyStats,
  fetchAgentProfile,
  fetchMultiLeaderboard,
  fetchCDNStats,
  fetchZKProofs,
  verifyZKP,
  bloomCheck,
  searchCatalog,
  getAgentCatalog,
  registerCatalog,
  subscribeCatalog,
  fetchRoutingStrategies,
  suggestPrice,
  fetchDemandForMe,
  fetchMCPHealth,
  fetchWalletBalance,
  fetchWalletHistory,
  createDeposit,
  createTransfer,
  registerOpenClawWebhook,
  fetchOpenClawWebhooks,
  deleteOpenClawWebhook,
  testOpenClawWebhook,
  fetchOpenClawStatus,
  creatorRegister,
  creatorLogin,
  fetchCreatorProfile,
  updateCreatorProfile,
  fetchCreatorAgents,
  claimAgent,
  fetchCreatorDashboard,
  fetchCreatorWallet,
  createRedemption,
  fetchRedemptions,
  cancelRedemption,
  fetchRedemptionMethods,
} from "../api";

describe("api.ts", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      } as Response)
    );
  });

  describe("get() helper", () => {
    test("constructs URL with BASE=/api/v1", async () => {
      await fetchHealth();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/health")
      );
    });

    test("appends query params to URL", async () => {
      await fetchAgents({ agent_type: "seller", page: 2 });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("agent_type=seller");
      expect(call).toContain("page=2");
    });

    test("skips undefined and null params", async () => {
      await fetchAgents({ agent_type: undefined, status: "active" });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).not.toContain("agent_type");
      expect(call).toContain("status=active");
    });

    test("throws on non-ok response", async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          text: () => Promise.resolve("Internal Server Error"),
        } as Response)
      );

      await expect(fetchHealth()).rejects.toThrow("API 500: Internal Server Error");
    });

    test("returns parsed JSON", async () => {
      const mockData = { status: "healthy" };
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockData),
        } as Response)
      );

      const result = await fetchHealth();
      expect(result).toEqual(mockData);
    });
  });

  describe("authGet() helper", () => {
    test("adds Authorization Bearer header", async () => {
      await fetchTransactions("test-token-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: { Authorization: "Bearer test-token-123" },
        })
      );
    });

    test("passes query params", async () => {
      await fetchTransactions("token", { status: "completed", page: 1 });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("status=completed");
      expect(call).toContain("page=1");
    });

    test("throws on error response", async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          text: () => Promise.resolve("Unauthorized"),
        } as Response)
      );

      await expect(fetchMyEarnings("invalid-token")).rejects.toThrow(
        "API 401: Unauthorized"
      );
    });
  });

  describe("authPost() helper", () => {
    test("uses POST method", async () => {
      await autoMatch("token", { description: "test" });
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: "POST" })
      );
    });

    test("sends JSON body", async () => {
      const body = { description: "test", category: "ai-models" };
      await autoMatch("token", body);
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: JSON.stringify(body),
        })
      );
    });

    test("sets Content-Type header", async () => {
      await autoMatch("token", { description: "test" });
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        })
      );
    });

    test("adds Authorization header", async () => {
      await autoMatch("my-token", { description: "test" });
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer my-token",
          }),
        })
      );
    });
  });

  describe("authDelete() helper", () => {
    test("uses DELETE method", async () => {
      await deleteOpenClawWebhook("token", "webhook-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ method: "DELETE" })
      );
    });

    test("adds auth header", async () => {
      await deleteOpenClawWebhook("my-token", "webhook-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: { Authorization: "Bearer my-token" },
        })
      );
    });

    test("constructs correct URL", async () => {
      await deleteOpenClawWebhook("token", "webhook-456");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/integrations/openclaw/webhooks/webhook-456"),
        expect.any(Object)
      );
    });
  });

  describe("named exports", () => {
    test("fetchHealth calls correct endpoint", async () => {
      await fetchHealth();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/health")
      );
    });

    test("fetchAgents calls correct endpoint", async () => {
      await fetchAgents();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/agents")
      );
    });

    test("fetchListings calls correct endpoint", async () => {
      await fetchListings({ category: "ai-models" });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/listings");
      expect(call).toContain("category=ai-models");
    });

    test("fetchDiscover passes params", async () => {
      await fetchDiscover({ q: "search term", page: 1 });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/discover");
      expect(call).toContain("q=search+term");
    });

    test("fetchLeaderboard with limit", async () => {
      await fetchLeaderboard(10);
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/reputation/leaderboard");
      expect(call).toContain("limit=10");
    });

    test("fetchReputation with agentId", async () => {
      await fetchReputation("agent-123");
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/reputation/agent-123");
      expect(call).toContain("recalculate=true");
    });

    test("expressBuy uses authPost", async () => {
      await expressBuy("token", "listing-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/express/listing-123"),
        expect.objectContaining({
          method: "POST",
          headers: {
            Authorization: "Bearer token",
            "Content-Type": "application/json",
          },
        })
      );
    });

    test("fetchTrending with params", async () => {
      await fetchTrending(20, 24);
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/analytics/trending");
      expect(call).toContain("limit=20");
      expect(call).toContain("hours=24");
    });

    test("fetchDemandGaps with params", async () => {
      await fetchDemandGaps(5, "datasets");
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/analytics/demand-gaps");
      expect(call).toContain("limit=5");
      expect(call).toContain("category=datasets");
    });

    test("fetchOpportunities with params", async () => {
      await fetchOpportunities(10, "models");
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/analytics/opportunities");
      expect(call).toContain("limit=10");
      expect(call).toContain("category=models");
    });

    test("fetchMyStats uses authGet", async () => {
      await fetchMyStats("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/analytics/my-stats"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("fetchAgentProfile with agentId", async () => {
      await fetchAgentProfile("agent-456");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/analytics/agent/agent-456/profile")
      );
    });

    test("fetchMultiLeaderboard with boardType", async () => {
      await fetchMultiLeaderboard("buyers", 15);
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/analytics/leaderboard/buyers");
      expect(call).toContain("limit=15");
    });

    test("fetchCDNStats calls correct endpoint", async () => {
      await fetchCDNStats();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/health/cdn")
      );
    });

    test("fetchZKProofs with listingId", async () => {
      await fetchZKProofs("listing-789");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/zkp/listing-789/proofs")
      );
    });

    test("verifyZKP uses authPost", async () => {
      await verifyZKP("token", "listing-123", { keywords: ["test"] });
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/zkp/listing-123/verify"),
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer token",
          }),
        })
      );
    });

    test("bloomCheck with word param", async () => {
      await bloomCheck("listing-123", "medical");
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/zkp/listing-123/bloom-check");
      expect(call).toContain("word=medical");
    });

    test("searchCatalog with multiple params", async () => {
      await searchCatalog({ q: "api", namespace: "web3", max_price: 100 });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/catalog/search");
      expect(call).toContain("q=api");
      expect(call).toContain("namespace=web3");
      expect(call).toContain("max_price=100");
    });

    test("getAgentCatalog with agentId", async () => {
      await getAgentCatalog("agent-999");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/catalog/agent/agent-999")
      );
    });

    test("registerCatalog uses authPost", async () => {
      const body = { namespace: "ml", topic: "inference" };
      await registerCatalog("token", body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/catalog"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(body),
        })
      );
    });

    test("subscribeCatalog uses authPost", async () => {
      const body = { namespace_pattern: "ai.*", max_price: 50 };
      await subscribeCatalog("token", body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/catalog/subscribe"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(body),
        })
      );
    });

    test("fetchRoutingStrategies calls correct endpoint", async () => {
      await fetchRoutingStrategies();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/route/strategies")
      );
    });

    test("suggestPrice uses authPost", async () => {
      await suggestPrice("token", { category: "datasets", quality_score: 85 });
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/seller/price-suggest"),
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    test("fetchDemandForMe uses authGet", async () => {
      await fetchDemandForMe("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/seller/demand-for-me"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("fetchMCPHealth calls /mcp/health", async () => {
      await fetchMCPHealth();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/mcp/health")
      );
    });

    test("fetchWalletBalance uses authGet", async () => {
      await fetchWalletBalance("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/wallet/balance"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("fetchWalletHistory with params", async () => {
      await fetchWalletHistory("token", { page: 2, tx_type: "deposit" });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/wallet/history");
      expect(call).toContain("page=2");
      expect(call).toContain("tx_type=deposit");
    });

    test("createDeposit uses authPost", async () => {
      await createDeposit("token", { amount_usd: 100 });
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/wallet/deposit"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ amount_usd: 100 }),
        })
      );
    });

    test("createTransfer uses authPost", async () => {
      const body = { to_agent_id: "agent-123", amount: 50, memo: "payment" };
      await createTransfer("token", body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/wallet/transfer"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(body),
        })
      );
    });

    test("registerOpenClawWebhook uses authPost", async () => {
      const body = {
        gateway_url: "https://example.com",
        bearer_token: "token",
        event_types: ["listing.created"],
        filters: {},
      };
      await registerOpenClawWebhook("token", body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/integrations/openclaw/register-webhook"),
        expect.objectContaining({ method: "POST" })
      );
    });

    test("fetchOpenClawWebhooks uses authGet", async () => {
      await fetchOpenClawWebhooks("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/integrations/openclaw/webhooks"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("testOpenClawWebhook uses authPost", async () => {
      await testOpenClawWebhook("token", "webhook-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/integrations/openclaw/webhooks/webhook-123/test"),
        expect.objectContaining({ method: "POST" })
      );
    });

    test("fetchOpenClawStatus uses authGet", async () => {
      await fetchOpenClawStatus("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/integrations/openclaw/status"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("creatorRegister calls correct endpoint", async () => {
      const body = {
        email: "test@example.com",
        password: "pass123",
        display_name: "Test User",
      };
      await creatorRegister(body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/register"),
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
      );
    });

    test("creatorLogin calls correct endpoint", async () => {
      const body = { email: "test@example.com", password: "pass123" };
      await creatorLogin(body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/login"),
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
      );
    });

    test("creatorRegister throws on error", async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          text: () => Promise.resolve("Email already exists"),
        } as Response)
      );

      await expect(
        creatorRegister({
          email: "test@example.com",
          password: "pass",
          display_name: "Test",
        })
      ).rejects.toThrow("API 400: Email already exists");
    });

    test("creatorLogin throws on error", async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 401,
          text: () => Promise.resolve("Invalid credentials"),
        } as Response)
      );

      await expect(
        creatorLogin({ email: "test@example.com", password: "wrong" })
      ).rejects.toThrow("API 401: Invalid credentials");
    });

    test("fetchCreatorProfile uses authGet", async () => {
      await fetchCreatorProfile("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/me"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("updateCreatorProfile uses authPut", async () => {
      await updateCreatorProfile("token", { display_name: "New Name" });
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/me"),
        expect.objectContaining({ method: "PUT" })
      );
    });

    test("fetchCreatorAgents uses authGet", async () => {
      await fetchCreatorAgents("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/me/agents"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("claimAgent uses authPost", async () => {
      await claimAgent("token", "agent-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/me/agents/agent-123/claim"),
        expect.objectContaining({ method: "POST" })
      );
    });

    test("fetchCreatorDashboard uses authGet", async () => {
      await fetchCreatorDashboard("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/me/dashboard"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("fetchCreatorWallet uses authGet", async () => {
      await fetchCreatorWallet("token");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/creators/me/wallet"),
        expect.objectContaining({
          headers: { Authorization: "Bearer token" },
        })
      );
    });

    test("createRedemption uses authPost", async () => {
      const body = { redemption_type: "bank_transfer", amount_usd: 10.0 };
      await createRedemption("token", body);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/redemptions"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(body),
        })
      );
    });

    test("fetchRedemptions uses authGet with params", async () => {
      await fetchRedemptions("token", { status: "pending", page: 1 });
      const call = (fetch as any).mock.calls[0][0];
      expect(call).toContain("/api/v1/redemptions");
      expect(call).toContain("status=pending");
      expect(call).toContain("page=1");
    });

    test("cancelRedemption uses authPost", async () => {
      await cancelRedemption("token", "redemption-123");
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/redemptions/redemption-123/cancel"),
        expect.objectContaining({ method: "POST" })
      );
    });

    test("fetchRedemptionMethods calls correct endpoint", async () => {
      await fetchRedemptionMethods();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/redemptions/methods")
      );
    });
  });

  describe("error handling", () => {
    test("handles network errors", async () => {
      global.fetch = vi.fn(() => Promise.reject(new Error("Network error")));

      await expect(fetchHealth()).rejects.toThrow("Network error");
    });

    test("handles 404 responses", async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 404,
          text: () => Promise.resolve("Not Found"),
        } as Response)
      );

      await expect(fetchAgentProfile("non-existent")).rejects.toThrow(
        "API 404: Not Found"
      );
    });

    test("handles 403 responses", async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 403,
          text: () => Promise.resolve("Forbidden"),
        } as Response)
      );

      await expect(fetchMyEarnings("invalid-token")).rejects.toThrow(
        "API 403: Forbidden"
      );
    });
  });
});
