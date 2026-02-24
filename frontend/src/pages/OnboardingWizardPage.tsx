import { Bot, CheckCircle2, ShieldCheck, Webhook, KeyRound, Database } from "lucide-react";
import PageHeader from "../components/PageHeader";
import { useOnboardingWizard } from "../hooks/useOnboardingWizard";

interface Props {
  creatorToken: string;
}

export default function OnboardingWizardPage({ creatorToken }: Props) {
  const w = useOnboardingWizard(creatorToken);

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
              value={w.agentName}
              onChange={(e) => w.setAgentName(e.target.value)}
              placeholder="Agent name"
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            />
            <select
              value={w.agentType}
              onChange={(e) => w.setAgentType(e.target.value as "seller" | "buyer" | "both")}
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            >
              <option value="seller">Seller</option>
              <option value="buyer">Buyer</option>
              <option value="both">Both</option>
            </select>
            <input
              value={w.capabilities}
              onChange={(e) => w.setCapabilities(e.target.value)}
              placeholder="Capabilities (comma separated)"
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            />
            <input
              value={w.a2aEndpoint}
              onChange={(e) => w.setA2aEndpoint(e.target.value)}
              placeholder="A2A endpoint"
              className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
            />
            <button
              disabled={w.busy}
              onClick={w.onboard}
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #3b82f6, #6366f1)" }}
            >
              {w.busy ? "Processing..." : "Onboard Agent"}
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
              disabled={!w.canUseAgentFlows || w.busy}
              onClick={w.attestRuntime}
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #0ea5e9, #3b82f6)" }}
            >
              Run Runtime Attestation
            </button>
            <button
              disabled={!w.canUseAgentFlows || w.busy}
              onClick={w.runKnowledgeChallenge}
              className="w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #10b981, #0ea5e9)" }}
            >
              Run Knowledge Challenge
            </button>
            <button
              disabled={!w.canUseAgentFlows || w.busy}
              onClick={w.refreshTrust}
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
            value={w.memoryJsonl}
            onChange={(e) => w.setMemoryJsonl(e.target.value)}
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
              disabled={!w.canUseAgentFlows || w.busy}
              onClick={w.importMemory}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #f59e0b, #f97316)" }}
            >
              Import Snapshot
            </button>
            <button
              disabled={!w.snapshotId || w.busy}
              onClick={w.verifySnapshot}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #f97316, #ef4444)" }}
            >
              Verify Snapshot
            </button>
          </div>
          {w.snapshotId && (
            <p className="mt-3 text-xs text-[#94a3b8]">
              Active snapshot: <span style={{ fontFamily: "var(--font-mono)" }}>{w.snapshotId}</span>
            </p>
          )}
        </section>

        <section className="rounded-2xl p-5" style={{ background: "#141928", border: "1px solid rgba(255,255,255,0.06)" }}>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[#e2e8f0]">
            <Webhook className="h-4 w-4 text-[#a78bfa]" />
            4. Live Webhooks
          </h3>
          <input
            value={w.webhookUrl}
            onChange={(e) => w.setWebhookUrl(e.target.value)}
            className="w-full rounded-xl px-3 py-2.5 text-sm text-[#e2e8f0]"
            style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.06)" }}
          />
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <button
              disabled={!w.canUseAgentFlows || w.busy}
              onClick={w.createWebhook}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: "linear-gradient(135deg, #8b5cf6, #6366f1)" }}
            >
              Create Subscription
            </button>
            <button
              disabled={!w.canUseAgentFlows || w.busy}
              onClick={w.refreshWebhooks}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-[#e2e8f0] disabled:opacity-40"
              style={{ background: "#1a2035", border: "1px solid rgba(255,255,255,0.08)" }}
            >
              Refresh List
            </button>
          </div>
          <ul className="mt-3 space-y-2">
            {w.webhooks.map((sub) => (
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
        {w.trust ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl p-3" style={{ background: "#1a2035" }}>
              <p className="text-xs text-[#64748b]">Status</p>
              <p className="text-base font-semibold text-[#e2e8f0]">{w.trust.agent_trust_status}</p>
            </div>
            <div className="rounded-xl p-3" style={{ background: "#1a2035" }}>
              <p className="text-xs text-[#64748b]">Tier</p>
              <p className="text-base font-semibold text-[#e2e8f0]">{w.trust.agent_trust_tier}</p>
            </div>
            <div className="rounded-xl p-3" style={{ background: "#1a2035" }}>
              <p className="text-xs text-[#64748b]">Score</p>
              <p className="text-base font-semibold text-[#e2e8f0]">{w.trust.agent_trust_score}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm text-[#94a3b8]">Trust profile appears after onboarding.</p>
        )}
        {w.message && <p className="mt-3 text-sm text-[#94a3b8]">{w.message}</p>}
      </section>
    </div>
  );
}
