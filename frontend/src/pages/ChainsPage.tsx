import { useState } from "react";
import { Link2, Wand2, FolderOpen, History, RotateCcw } from "lucide-react";
import PageHeader from "../components/PageHeader";
import ComposeForm from "../components/chains/ComposeForm";
import ChainEditor from "../components/chains/ChainEditor";
import ChainExecutor from "../components/chains/ChainExecutor";
import ChainTemplateCard from "../components/chains/ChainTemplateCard";
import { useChainComposer } from "../hooks/useChainComposer";
import { useMyChains } from "../hooks/useMyChains";

type SubTab = "compose" | "my-chains" | "executions";

interface Props {
  agentToken: string;
  agentId: string;
}

const SUB_TABS: { id: SubTab; label: string; icon: typeof Wand2 }[] = [
  { id: "compose", label: "Compose", icon: Wand2 },
  { id: "my-chains", label: "My Chains", icon: FolderOpen },
  { id: "executions", label: "Executions", icon: History },
];

export default function ChainsPage({ agentToken, agentId }: Props) {
  const [subTab, setSubTab] = useState<SubTab>("compose");
  const composer = useChainComposer(agentToken);
  const myChains = useMyChains(agentToken, agentId);

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="Chain Composer"
        subtitle="Compose, save, and execute multi-agent chains from natural language"
        icon={Link2}
        actions={
          composer.phase !== "idle" ? (
            <button
              onClick={composer.reset}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-[#94a3b8] transition-colors hover:text-[#e2e8f0] hover:bg-[rgba(255,255,255,0.05)]"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Reset
            </button>
          ) : undefined
        }
      />

      {/* Sub-tab nav */}
      <div className="flex gap-1 rounded-xl p-1" style={{ backgroundColor: "rgba(255,255,255,0.03)" }}>
        {SUB_TABS.map((tab) => {
          const active = subTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setSubTab(tab.id)}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all"
              style={{
                color: active ? "#e2e8f0" : "#64748b",
                backgroundColor: active ? "rgba(96,165,250,0.1)" : "transparent",
              }}
            >
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Compose tab */}
      {subTab === "compose" && (
        <div
          className="rounded-2xl border p-5 space-y-6"
          style={{ backgroundColor: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
        >
          {/* Phase: idle or composing */}
          {(composer.phase === "idle" || composer.phase === "composing") && (
            <ComposeForm
              onCompose={composer.compose}
              loading={composer.phase === "composing"}
            />
          )}

          {/* Phase: editing or saving */}
          {(composer.phase === "editing" || composer.phase === "saving") && composer.composeResult && (
            <ChainEditor
              name={composer.editedName}
              onNameChange={composer.setEditedName}
              assignments={composer.editedAssignments}
              alternatives={composer.composeResult.alternatives}
              budget={composer.editedBudget}
              onBudgetChange={composer.setEditedBudget}
              onRemoveNode={composer.removeNode}
              onReplaceAgent={composer.replaceAgent}
              onSave={composer.saveTemplate}
              saving={composer.phase === "saving"}
              saveError={composer.phase === "editing" ? composer.error : null}
            />
          )}

          {/* Phase: done (saved) → execute */}
          {(composer.phase === "done" || composer.phase === "executing") && composer.savedTemplate && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
                style={{ borderColor: "rgba(52,211,153,0.3)", backgroundColor: "rgba(52,211,153,0.05)", color: "#34d399" }}
              >
                Template saved: <span className="font-mono text-xs">{composer.savedTemplate.id.slice(0, 12)}...</span>
              </div>
              <ChainExecutor
                onExecute={composer.executeTemplate}
                execution={composer.execution}
                executing={composer.phase === "executing"}
              />
            </div>
          )}

          {/* Phase: error */}
          {composer.phase === "error" && composer.error && (
            <div className="rounded-lg border px-4 py-3 text-sm"
              style={{ borderColor: "rgba(248,113,113,0.3)", backgroundColor: "rgba(248,113,113,0.05)", color: "#f87171" }}
            >
              {composer.error}
            </div>
          )}
        </div>
      )}

      {/* My Chains tab */}
      {subTab === "my-chains" && (
        <div>
          {myChains.loading && (
            <p className="text-sm text-[#64748b] py-8 text-center">Loading chains...</p>
          )}
          {myChains.error && (
            <p className="text-sm text-[#f87171] py-8 text-center">{myChains.error}</p>
          )}
          {!myChains.loading && myChains.chains.length === 0 && (
            <div className="text-center py-12 space-y-2">
              <p className="text-sm text-[#64748b]">No chains yet</p>
              <p className="text-xs text-[#475569]">
                Go to the Compose tab to create your first chain.
              </p>
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {myChains.chains.map((chain) => (
              <ChainTemplateCard
                key={chain.id}
                template={chain}
                onView={() => { /* future: detail modal */ }}
                onExecute={() => {
                  setSubTab("compose");
                  // Could pre-load the template for execution
                }}
                onArchive={async (id) => {
                  await myChains.archive(id);
                }}
              />
            ))}
          </div>
        </div>
      )}

      {/* Executions tab */}
      {subTab === "executions" && (
        <div className="text-center py-12 space-y-2">
          <History className="mx-auto h-8 w-8 text-[#334155]" />
          <p className="text-sm text-[#64748b]">Execution history</p>
          <p className="text-xs text-[#475569]">
            Executions will appear here after you run a chain from the Compose tab.
          </p>
        </div>
      )}
    </div>
  );
}
