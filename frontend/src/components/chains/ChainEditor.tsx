import { ArrowDown, X, Save, AlertTriangle } from "lucide-react";
import type { ChainAssignment, AgentSuggestion } from "../../types/chain";
import Badge from "../Badge";

const CAPABILITY_COLORS: Record<string, string> = {
  data: "blue",
  transform: "purple",
  analysis: "amber",
  compliance: "cyan",
  output: "green",
  test: "indigo",
  judge: "orange",
  review: "rose",
};

interface Props {
  name: string;
  onNameChange: (name: string) => void;
  assignments: ChainAssignment[];
  alternatives: Record<string, AgentSuggestion[]>;
  budget: number | null;
  onBudgetChange: (budget: number | null) => void;
  onRemoveNode: (index: number) => void;
  onReplaceAgent: (index: number, agentId: string, agentName: string, rankScore: number) => void;
  onSave: () => void;
  saving: boolean;
  saveError: string | null;
}

export default function ChainEditor({
  name, onNameChange,
  assignments, alternatives,
  budget, onBudgetChange,
  onRemoveNode, onReplaceAgent,
  onSave, saving, saveError,
}: Props) {
  return (
    <div className="space-y-4">
      {/* Chain name */}
      <div>
        <label className="mb-1 block text-xs text-[#94a3b8]">Chain name</label>
        <input
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          className="w-full rounded-lg border bg-transparent px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#60a5fa]"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        />
      </div>

      {/* Nodes */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-[#94a3b8] uppercase tracking-wider">Pipeline</p>
        {assignments.map((assignment, i) => {
          const alts = alternatives[assignment.capability] ?? [];
          return (
            <div key={`${assignment.capability}-${i}`}>
              <div
                className="flex items-center gap-3 rounded-xl border px-4 py-3"
                style={{ backgroundColor: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-[#60a5fa]"
                  style={{ backgroundColor: "rgba(96,165,250,0.15)" }}
                >
                  {i + 1}
                </span>
                <Badge
                  label={assignment.capability}
                  variant={(CAPABILITY_COLORS[assignment.capability] ?? "gray") as keyof typeof CAPABILITY_COLORS & string}
                />
                <div className="flex-1">
                  {alts.length > 1 ? (
                    <select
                      value={assignment.agent_id}
                      onChange={(e) => {
                        const agent = alts.find((a) => a.agent_id === e.target.value);
                        if (agent) onReplaceAgent(i, agent.agent_id, agent.name, agent.rank_score);
                      }}
                      className="w-full rounded-lg border bg-transparent px-2 py-1 text-sm text-[#e2e8f0] outline-none"
                      style={{ borderColor: "rgba(255,255,255,0.08)" }}
                    >
                      {alts.map((a) => (
                        <option key={a.agent_id} value={a.agent_id} style={{ backgroundColor: "#0d1220" }}>
                          {a.name} (score: {a.rank_score.toFixed(2)})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-sm text-[#e2e8f0]">
                      {assignment.agent_name}{" "}
                      <span className="text-[#475569]">(score: {assignment.rank_score.toFixed(2)})</span>
                    </span>
                  )}
                </div>
                <button
                  onClick={() => onRemoveNode(i)}
                  className="rounded-lg p-1 text-[#475569] hover:text-[#f87171] transition-colors"
                  title="Remove node"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              {i < assignments.length - 1 && (
                <div className="flex justify-center py-0.5">
                  <ArrowDown className="h-4 w-4 text-[#334155]" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {assignments.length === 0 && (
        <p className="text-center text-sm text-[#475569] py-6">
          All nodes removed. Go back and compose again.
        </p>
      )}

      {/* Budget */}
      <div>
        <label className="mb-1 block text-xs text-[#94a3b8]">Max budget (USD)</label>
        <input
          type="number"
          step="0.01"
          min="0"
          value={budget ?? ""}
          onChange={(e) => onBudgetChange(e.target.value ? parseFloat(e.target.value) : null)}
          placeholder="No limit"
          className="w-48 rounded-lg border bg-transparent px-3 py-2 text-sm text-[#e2e8f0] outline-none focus:border-[#60a5fa]"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        />
      </div>

      {/* Save */}
      {saveError && (
        <div className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
          style={{ borderColor: "rgba(251,191,36,0.3)", backgroundColor: "rgba(251,191,36,0.05)", color: "#fbbf24" }}
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {saveError}
        </div>
      )}

      <button
        onClick={onSave}
        disabled={saving || assignments.length === 0}
        className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium text-white transition-all disabled:opacity-40"
        style={{
          background: "linear-gradient(135deg, #34d399, #60a5fa)",
          boxShadow: "0 0 16px rgba(52,211,153,0.25)",
        }}
      >
        <Save className="h-4 w-4" />
        {saving ? "Saving..." : "Save as Template"}
      </button>
    </div>
  );
}
