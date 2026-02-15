import { useMemo, useState } from "react";
import { Bot, CheckCircle2, ShieldCheck, Webhook, KeyRound, Database } from "lucide-react";

import PageHeader from "../components/PageHeader";
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

interface Props {
  creatorToken: string;
}

function parseJsonl(input: string): Record<string, unknown>[] {
  return input
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => JSON.parse(line) as Record<string, unknown>);
}

export default function OnboardingWizardPage({ creatorToken }: Props) {
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
    if (!agentId) return;
    const profile = await fetchAgentTrustV2(agentId);
    setTrust(profile);
  };

  const refreshWebhooks = async () => {
    if (!agentToken) return;
    const data = await fetchWebhookSubscriptionsV2(agentToken);
    setWebhooks(data.subscriptions ?? []);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Agent Onboarding Wizard"
        subtitle="No-code flow: onboard, attest knowledge, verify memory, and enable webhook delivery"
        icon={ShieldCheck}
      />

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl p-5" style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
            <Bot className="h-4 w-4 text-[#60a5fa]" />
            1. Onboard Agent
          </h3>

          <div className="space-y-3">
            <input
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
              placeholder="Agent name"
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            />
            <select
              value={agentType}
              onChange={(e) => setAgentType(e.target.value as "seller" | "buyer" | "both")}
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            >
              <option value="seller">Seller</option>
              <option value="buyer">Buyer</option>
              <option value="both">Both</option>
            </select>
            <input
              value={capabilities}
              onChange={(e) => setCapabilities(e.target.value)}
              placeholder="Capabilities (comma separated)"
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            />
            <input
              value={a2aEndpoint}
              onChange={(e) => setA2aEndpoint(e.target.value)}
              placeholder="A2A endpoint"
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            />
            <button
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const onboarded = await onboardAgentV2(creatorToken, {
                    name: agentName.trim(),
                    description: "Onboarded via no-code wizard",
                    agent_type: agentType,
                    public_key:
                      "ssh-rsa AAAA_test_registration_key_placeholder_long_enough",
                    capabilities: capabilities
                      .split(",")
                      .map((v) => v.trim())
                      .filter(Boolean),
                    a2a_endpoint: a2aEndpoint.trim(),
                    memory_import_intent: true,
                  });
                  setAgentId(onboarded.agent_id);
                  setAgentToken(onboarded.agent_jwt_token);
                  setTrust(onboarded);
                  setMessage("Agent onboarded. Continue with runtime and knowledge checks.");
                })
              }
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}
            >
              {busy ? "Processing..." : "Onboard Agent"}
            </button>
          </div>
        </section>

        <section className="rounded-2xl p-5" style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
            <CheckCircle2 className="h-4 w-4 text-[#34d399]" />
            2. Runtime + Knowledge Attestation
          </h3>
          <div className="space-y-3">
            <button
              disabled={!canUseAgentFlows || busy}
              onClick={() =>
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
                })
              }
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #0ea5e9, #3b82f6)" }}
            >
              Run Runtime Attestation
            </button>
            <button
              disabled={!canUseAgentFlows || busy}
              onClick={() =>
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
                })
              }
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #10b981, #0ea5e9)" }}
            >
              Run Knowledge Challenge
            </button>
            <button
              disabled={!canUseAgentFlows || busy}
              onClick={() => run(refreshTrust)}
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-[#e2e8f0] disabled:opacity-40"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.08)" }}
            >
              Refresh Trust Profile
            </button>
          </div>
        </section>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="rounded-2xl p-5" style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
            <Database className="h-4 w-4 text-[#f59e0b]" />
            3. Memory Import + Verify
          </h3>
          <textarea
            value={memoryJsonl}
            onChange={(e) => setMemoryJsonl(e.target.value)}
            rows={7}
            className="w-full rounded-xl px-3 py-2.5 text-xs text-[#e2e8f0]"
            style={{
              background: "#1a2035",
              border: "1px solid rgba(255,255,255,0.06)",
              fontFamily: "var(--font-mono)",
            }}
          />
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <button
              disabled={!canUseAgentFlows || busy}
              onClick={() =>
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
                })
              }
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #f59e0b, #f97316)" }}
            >
              Import Snapshot
            </button>
            <button
              disabled={!snapshotId || busy}
              onClick={() =>
                run(async () => {
                  const result = await verifyMemorySnapshotV2(agentToken, snapshotId, {
                    sample_size: 2,
                  });
                  setTrust(result.trust_profile);
                  setMessage(`Snapshot verification status: ${result.status}`);
                })
              }
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #f97316, #ef4444)" }}
            >
              Verify Snapshot
            </button>
          </div>
          {snapshotId && (
            <p className="mt-3 text-xs text-[#94a3b8]">
              Active snapshot: <span style={{ fontFamily: "var(--font-mono)" }}>{snapshotId}</span>
            </p>
          )}
        </section>

        <section className="rounded-2xl p-5" style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
            <Webhook className="h-4 w-4 text-[#a78bfa]" />
            4. Live Webhooks
          </h3>
          <input
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
            className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
            style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
          />
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <button
              disabled={!canUseAgentFlows || busy}
              onClick={() =>
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
                })
              }
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #8b5cf6, #6366f1)" }}
            >
              Create Subscription
            </button>
            <button
              disabled={!canUseAgentFlows || busy}
              onClick={() => run(refreshWebhooks)}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-[#e2e8f0] disabled:opacity-40"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.08)" }}
            >
              Refresh List
            </button>
          </div>
          <ul className="mt-3 space-y-2">
            {webhooks.map((sub) => (
              <li
                key={sub.id}
                className="rounded-lg px-3 py-2 text-xs text-[#cbd5e1]"
                style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
              >
                {sub.callback_url} ({sub.status})
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className="rounded-2xl p-5" style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
          <KeyRound className="h-4 w-4 text-[#60a5fa]" />
          Trust Status
        </h3>
        {trust ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl p-3" style={{ background: "#1a2035" }}>
              <p className="text-xs text-[#64748b]">Status</p>
              <p className="text-base font-semibold text-[#e2e8f0]">{trust.agent_trust_status}</p>
            </div>
            <div className="rounded-xl p-3" style={{ background: "#1a2035" }}>
              <p className="text-xs text-[#64748b]">Tier</p>
              <p className="text-base font-semibold text-[#e2e8f0]">{trust.agent_trust_tier}</p>
            </div>
            <div className="rounded-xl p-3" style={{ background: "#1a2035" }}>
              <p className="text-xs text-[#64748b]">Score</p>
              <p className="text-base font-semibold text-[#e2e8f0]">{trust.agent_trust_score}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-[#94a3b8]">Trust profile appears after onboarding.</p>
        )}
        {message && <p className="mt-3 text-sm text-[#94a3b8]">{message}</p>}
      </section>
    </div>
  );
}
