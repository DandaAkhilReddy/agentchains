import { useMemo, useState } from "react";
import {
  attestRuntimeV2,
  createWebhookSubscriptionV2,
  fetchAgentTrustV2,
  fetchWebhookSubscriptionsV2,
  importMemorySnapshotV2,
  onboardAgentV2,
  runKnowledgeChallengeV2,
  verifyMemorySnapshotV2,
} from "../lib/api";
import type { AgentTrustProfile, WebhookSubscription } from "../types/api";

function parseJsonl(input: string): Record<string, unknown>[] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

export function useOnboardingWizard(creatorToken: string, onAgentCreated?: (token: string, id: string) => void) {
  const [agentName, setAgentName] = useState(`agent-${Math.random().toString(16).slice(2, 8)}`);
  const [agentType, setAgentType] = useState<"seller" | "buyer" | "both">("both");
  const [capabilities, setCapabilities] = useState("retrieval,tool_use");
  const [a2aEndpoint, setA2aEndpoint] = useState("https://agent.example.com");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const [agentId, setAgentId] = useState("");
  const [agentToken, setAgentToken] = useState("");
  const [trust, setTrust] = useState<AgentTrustProfile | null>(null);

  const [memoryJsonl, setMemoryJsonl] = useState(
    '{"id":"mem-1","content":"Market demand summary","source":"firecrawl"}\n{"id":"mem-2","content":"Pricing signal","source":"firecrawl"}',
  );
  const [snapshotId, setSnapshotId] = useState("");

  const [webhookUrl, setWebhookUrl] = useState("https://example.com/hooks/agentchains");
  const [webhooks, setWebhooks] = useState<WebhookSubscription[]>([]);

  const canUseAgentFlows = useMemo(() => Boolean(agentId && agentToken), [agentId, agentToken]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setMessage("");
    try {
      await fn();
    } catch (err) {
      const text = err instanceof Error ? err.message : "Unexpected error";
      setMessage(text);
    } finally {
      setBusy(false);
    }
  };

  const refreshTrust = async () => {
    if (!agentId || !agentToken) return;
    const profile = await fetchAgentTrustV2(agentId, agentToken);
    setTrust(profile);
  };

  const refreshWebhooks = async () => {
    if (!agentToken) return;
    const data = await fetchWebhookSubscriptionsV2(agentToken);
    setWebhooks(data.subscriptions ?? []);
  };

  const onboard = () =>
    run(async () => {
      const onboarded = await onboardAgentV2(creatorToken, {
        name: agentName.trim(),
        description: "Onboarded via no-code wizard",
        agent_type: agentType,
        public_key: "ssh-rsa AAAA_test_registration_key_placeholder_long_enough",
        capabilities: capabilities.split(",").map((v) => v.trim()).filter(Boolean),
        a2a_endpoint: a2aEndpoint.trim(),
        memory_import_intent: true,
      });
      setAgentId(onboarded.agent_id);
      setAgentToken(onboarded.agent_jwt_token);
      setTrust(onboarded);
      onAgentCreated?.(onboarded.agent_jwt_token, onboarded.agent_id);
      setMessage("Agent onboarded. Continue with runtime and knowledge checks.");
    });

  const attestRuntime = () =>
    run(async () => {
      await attestRuntimeV2(agentToken, agentId, {
        runtime_name: "agent-runtime",
        runtime_version: "1.0.0",
        sdk_version: "0.1.0",
        endpoint_reachable: true,
        supports_memory: true,
      });
      setMessage("Runtime attestation completed.");
      await refreshTrust();
    });

  const runKnowledgeChallenge = () =>
    run(async () => {
      await runKnowledgeChallengeV2(agentToken, agentId, {
        capabilities: ["retrieval", "tool_use"],
        claim_payload: {
          citations_present: true,
          schema_valid: true,
          adversarial_resilience: true,
          reproducible: true,
          freshness_ok: true,
          tool_constraints_ok: true,
          sample_output: "Safe output with citations and schema-compliant response.",
        },
      });
      setMessage("Knowledge challenge completed.");
      await refreshTrust();
    });

  const importMemory = () =>
    run(async () => {
      const records = parseJsonl(memoryJsonl);
      const result = await importMemorySnapshotV2(agentToken, {
        source_type: "sdk",
        label: "wizard-import",
        records,
        chunk_size: 2,
      });
      setSnapshotId(result.snapshot.snapshot_id);
      setTrust(result.trust_profile);
      setMessage(`Snapshot imported: ${result.snapshot.snapshot_id}`);
    });

  const verifySnapshot = () =>
    run(async () => {
      const result = await verifyMemorySnapshotV2(agentToken, snapshotId, {
        sample_size: 2,
      });
      setTrust(result.trust_profile);
      setMessage(`Snapshot verification status: ${result.status}`);
    });

  const createWebhook = () =>
    run(async () => {
      await createWebhookSubscriptionV2(agentToken, {
        callback_url: webhookUrl.trim(),
        event_types: [
          "agent.trust.updated",
          "memory.snapshot.verified",
          "challenge.failed",
          "challenge.passed",
        ],
      });
      setMessage("Webhook subscription created.");
      await refreshWebhooks();
    });

  return {
    // Form state
    agentName, setAgentName,
    agentType, setAgentType,
    capabilities, setCapabilities,
    a2aEndpoint, setA2aEndpoint,
    memoryJsonl, setMemoryJsonl,
    webhookUrl, setWebhookUrl,

    // Derived state
    busy, message, canUseAgentFlows,
    trust, snapshotId, webhooks,

    // Actions
    onboard,
    attestRuntime,
    runKnowledgeChallenge,
    refreshTrust: () => run(refreshTrust),
    importMemory,
    verifySnapshot,
    createWebhook,
    refreshWebhooks: () => run(refreshWebhooks),
  };
}
