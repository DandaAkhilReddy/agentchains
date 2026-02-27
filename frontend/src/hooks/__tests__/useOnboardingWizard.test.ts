import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";

// Mock all API functions used by useOnboardingWizard
vi.mock("../../lib/api", () => ({
  attestRuntimeV2: vi.fn(),
  createWebhookSubscriptionV2: vi.fn(),
  fetchAgentTrustV2: vi.fn(),
  fetchWebhookSubscriptionsV2: vi.fn(),
  importMemorySnapshotV2: vi.fn(),
  onboardAgentV2: vi.fn(),
  runKnowledgeChallengeV2: vi.fn(),
  verifyMemorySnapshotV2: vi.fn(),
}));

import {
  attestRuntimeV2,
  createWebhookSubscriptionV2,
  fetchAgentTrustV2,
  fetchWebhookSubscriptionsV2,
  importMemorySnapshotV2,
  onboardAgentV2,
  runKnowledgeChallengeV2,
  verifyMemorySnapshotV2,
} from "../../lib/api";

const mockOnboardAgentV2 = vi.mocked(onboardAgentV2);
const mockAttestRuntimeV2 = vi.mocked(attestRuntimeV2);
const mockRunKnowledgeChallengeV2 = vi.mocked(runKnowledgeChallengeV2);
const mockFetchAgentTrustV2 = vi.mocked(fetchAgentTrustV2);
const mockFetchWebhookSubscriptionsV2 = vi.mocked(fetchWebhookSubscriptionsV2);
const mockImportMemorySnapshotV2 = vi.mocked(importMemorySnapshotV2);
const mockVerifyMemorySnapshotV2 = vi.mocked(verifyMemorySnapshotV2);
const mockCreateWebhookSubscriptionV2 = vi.mocked(createWebhookSubscriptionV2);

describe("useOnboardingWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  async function getHook(token = "creator-token") {
    const { useOnboardingWizard } = await import("../useOnboardingWizard");
    return renderHook(() => useOnboardingWizard(token));
  }

  it("initializes with default form state", async () => {
    const { result } = await getHook();

    expect(result.current.agentType).toBe("both");
    expect(result.current.capabilities).toBe("retrieval,tool_use");
    expect(result.current.a2aEndpoint).toBe("https://agent.example.com");
    expect(result.current.busy).toBe(false);
    expect(result.current.message).toBe("");
    expect(result.current.canUseAgentFlows).toBe(false);
    expect(result.current.trust).toBeNull();
    expect(result.current.snapshotId).toBe("");
    expect(result.current.webhooks).toEqual([]);
  });

  it("initializes agentName with random hex suffix", async () => {
    const { result } = await getHook();
    expect(result.current.agentName).toMatch(/^agent-[0-9a-f]{6}$/);
  });

  it("setAgentName updates agent name", async () => {
    const { result } = await getHook();
    act(() => {
      result.current.setAgentName("my-test-agent");
    });
    expect(result.current.agentName).toBe("my-test-agent");
  });

  it("setAgentType updates agent type", async () => {
    const { result } = await getHook();
    act(() => {
      result.current.setAgentType("seller");
    });
    expect(result.current.agentType).toBe("seller");
  });

  it("canUseAgentFlows is false when agentId or agentToken is empty", async () => {
    const { result } = await getHook();
    expect(result.current.canUseAgentFlows).toBe(false);
  });

  it("onboard calls onboardAgentV2 and sets agentId, agentToken, trust", async () => {
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-123",
      agent_jwt_token: "jwt-abc",
      display_name: "Test",
      trust_tier: "T1",
      trust_score: 0.5,
      trust_status: "verified",
    } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });

    await waitFor(() => {
      expect(result.current.busy).toBe(false);
    });

    expect(mockOnboardAgentV2).toHaveBeenCalledTimes(1);
    expect(result.current.message).toBe(
      "Agent onboarded. Continue with runtime and knowledge checks.",
    );
    expect(result.current.canUseAgentFlows).toBe(true);
  });

  it("onboard sets error message on failure", async () => {
    mockOnboardAgentV2.mockRejectedValueOnce(new Error("Network failure"));

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });

    await waitFor(() => {
      expect(result.current.busy).toBe(false);
    });

    expect(result.current.message).toBe("Network failure");
  });

  it("onboard handles non-Error thrown values", async () => {
    mockOnboardAgentV2.mockRejectedValueOnce("string error");

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });

    await waitFor(() => {
      expect(result.current.busy).toBe(false);
    });

    expect(result.current.message).toBe("Unexpected error");
  });

  it("attestRuntime calls attestRuntimeV2 and refreshes trust", async () => {
    // First onboard to get agentId/token
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-xyz",
      agent_jwt_token: "token-xyz",
    } as never);
    mockAttestRuntimeV2.mockResolvedValueOnce(undefined as never);
    mockFetchAgentTrustV2.mockResolvedValueOnce({ trust_tier: "T2" } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });

    await waitFor(() => expect(result.current.canUseAgentFlows).toBe(true));

    await act(async () => {
      await result.current.attestRuntime();
    });

    await waitFor(() => {
      expect(result.current.busy).toBe(false);
    });

    expect(mockAttestRuntimeV2).toHaveBeenCalledTimes(1);
    expect(result.current.message).toBe("Runtime attestation completed.");
  });

  it("runKnowledgeChallenge calls the API and refreshes trust", async () => {
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-kc",
      agent_jwt_token: "token-kc",
    } as never);
    mockRunKnowledgeChallengeV2.mockResolvedValueOnce(undefined as never);
    mockFetchAgentTrustV2.mockResolvedValueOnce({ trust_tier: "T2" } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });
    await waitFor(() => expect(result.current.canUseAgentFlows).toBe(true));

    await act(async () => {
      await result.current.runKnowledgeChallenge();
    });
    await waitFor(() => expect(result.current.busy).toBe(false));

    expect(mockRunKnowledgeChallengeV2).toHaveBeenCalledTimes(1);
    expect(result.current.message).toBe("Knowledge challenge completed.");
  });

  it("refreshTrust returns early when agentId is empty (covers line 58 branch)", async () => {
    // No onboarding done — agentId and agentToken are both ""
    const { result } = await getHook();

    // refreshTrust is wrapped in run() in the hook's returned object
    await act(async () => {
      await result.current.refreshTrust();
    });

    await waitFor(() => expect(result.current.busy).toBe(false));

    // fetchAgentTrustV2 should NOT have been called because agentId is empty
    expect(mockFetchAgentTrustV2).not.toHaveBeenCalled();
    // Message stays empty — early return before any side-effects
    expect(result.current.message).toBe("");
  });

  it("refreshTrust returns early when agentToken is empty (covers line 58 branch)", async () => {
    // Manually set agentName but don't onboard — agentId and agentToken remain ""
    const { result } = await getHook();

    act(() => {
      result.current.setAgentName("test-agent");
    });

    await act(async () => {
      await result.current.refreshTrust();
    });

    await waitFor(() => expect(result.current.busy).toBe(false));

    expect(mockFetchAgentTrustV2).not.toHaveBeenCalled();
  });

  it("refreshWebhooks returns early when agentToken is empty (covers line 64 branch)", async () => {
    const { result } = await getHook();

    // No onboarding — agentToken is ""
    await act(async () => {
      await result.current.refreshWebhooks();
    });

    await waitFor(() => expect(result.current.busy).toBe(false));

    // fetchWebhookSubscriptionsV2 should NOT have been called
    expect(mockFetchWebhookSubscriptionsV2).not.toHaveBeenCalled();
    expect(result.current.webhooks).toEqual([]);
  });

  it("importMemory parses JSONL and calls importMemorySnapshotV2", async () => {
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-mem",
      agent_jwt_token: "token-mem",
    } as never);
    mockImportMemorySnapshotV2.mockResolvedValueOnce({
      snapshot: { snapshot_id: "snap-001" },
      trust_profile: { trust_tier: "T2" },
    } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });
    await waitFor(() => expect(result.current.canUseAgentFlows).toBe(true));

    await act(async () => {
      await result.current.importMemory();
    });
    await waitFor(() => expect(result.current.busy).toBe(false));

    expect(mockImportMemorySnapshotV2).toHaveBeenCalledTimes(1);
    expect(result.current.snapshotId).toBe("snap-001");
    expect(result.current.message).toContain("snap-001");
  });

  it("verifySnapshot calls verifyMemorySnapshotV2", async () => {
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-vs",
      agent_jwt_token: "token-vs",
    } as never);
    mockImportMemorySnapshotV2.mockResolvedValueOnce({
      snapshot: { snapshot_id: "snap-002" },
      trust_profile: { trust_tier: "T1" },
    } as never);
    mockVerifyMemorySnapshotV2.mockResolvedValueOnce({
      status: "verified",
      trust_profile: { trust_tier: "T2" },
    } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });
    await waitFor(() => expect(result.current.canUseAgentFlows).toBe(true));

    await act(async () => {
      await result.current.importMemory();
    });
    await waitFor(() => expect(result.current.snapshotId).toBe("snap-002"));

    await act(async () => {
      await result.current.verifySnapshot();
    });
    await waitFor(() => expect(result.current.busy).toBe(false));

    expect(mockVerifyMemorySnapshotV2).toHaveBeenCalledTimes(1);
    expect(result.current.message).toContain("verified");
  });

  it("createWebhook calls createWebhookSubscriptionV2 and refreshes webhooks", async () => {
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-wh",
      agent_jwt_token: "token-wh",
    } as never);
    mockCreateWebhookSubscriptionV2.mockResolvedValueOnce(undefined as never);
    mockFetchWebhookSubscriptionsV2.mockResolvedValueOnce({
      subscriptions: [{ id: "wh-1", callback_url: "https://example.com" }],
    } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });
    await waitFor(() => expect(result.current.canUseAgentFlows).toBe(true));

    await act(async () => {
      await result.current.createWebhook();
    });
    await waitFor(() => expect(result.current.busy).toBe(false));

    expect(mockCreateWebhookSubscriptionV2).toHaveBeenCalledTimes(1);
    expect(result.current.message).toBe("Webhook subscription created.");
    expect(result.current.webhooks).toHaveLength(1);
  });

  it("setWebhookUrl updates webhook URL", async () => {
    const { result } = await getHook();
    act(() => {
      result.current.setWebhookUrl("https://my.hooks.io/endpoint");
    });
    expect(result.current.webhookUrl).toBe("https://my.hooks.io/endpoint");
  });

  it("setMemoryJsonl updates memory JSONL content", async () => {
    const { result } = await getHook();
    act(() => {
      result.current.setMemoryJsonl('{"id":"m-1","content":"test"}');
    });
    expect(result.current.memoryJsonl).toBe('{"id":"m-1","content":"test"}');
  });

  it("setCapabilities updates capabilities string", async () => {
    const { result } = await getHook();
    act(() => {
      result.current.setCapabilities("retrieval");
    });
    expect(result.current.capabilities).toBe("retrieval");
  });

  it("setA2aEndpoint updates A2A endpoint", async () => {
    const { result } = await getHook();
    act(() => {
      result.current.setA2aEndpoint("https://agent.prod.example.com");
    });
    expect(result.current.a2aEndpoint).toBe("https://agent.prod.example.com");
  });

  it("refreshWebhooks falls back to empty array when subscriptions is undefined (covers line 66 ?? [])", async () => {
    // Onboard to get an agentToken
    mockOnboardAgentV2.mockResolvedValueOnce({
      agent_id: "agent-wb",
      agent_jwt_token: "token-wb",
    } as never);

    // fetchWebhookSubscriptionsV2 returns object with no subscriptions field
    mockFetchWebhookSubscriptionsV2.mockResolvedValueOnce({
      subscriptions: undefined,
    } as never);

    const { result } = await getHook();

    await act(async () => {
      await result.current.onboard();
    });
    await waitFor(() => expect(result.current.canUseAgentFlows).toBe(true));

    await act(async () => {
      await result.current.refreshWebhooks();
    });
    await waitFor(() => expect(result.current.busy).toBe(false));

    expect(mockFetchWebhookSubscriptionsV2).toHaveBeenCalledTimes(1);
    // The ?? [] fallback means webhooks stays as empty array
    expect(result.current.webhooks).toEqual([]);
  });
});
