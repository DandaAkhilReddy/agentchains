import { useState } from "react";
import { Play, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import type { ChainExecution } from "../../types/chain";
import Badge from "../Badge";

interface Props {
  onExecute: (inputData: Record<string, unknown>) => Promise<void>;
  execution: ChainExecution | null;
  executing: boolean;
}

export default function ChainExecutor({ onExecute, execution, executing }: Props) {
  const [inputJson, setInputJson] = useState("{}");
  const [parseError, setParseError] = useState<string | null>(null);

  const handleExecute = async () => {
    setParseError(null);
    try {
      const parsed = JSON.parse(inputJson);
      await onExecute(parsed);
    } catch {
      setParseError("Invalid JSON input");
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="h-5 w-5 text-[#34d399]" />;
      case "failed": return <XCircle className="h-5 w-5 text-[#f87171]" />;
      default: return <Loader2 className="h-5 w-5 text-[#60a5fa] animate-spin" />;
    }
  };

  const statusVariant = (status: string) => {
    switch (status) {
      case "completed": return "green";
      case "failed": return "red";
      case "running": return "blue";
      default: return "gray";
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1.5 block text-sm font-medium text-[#e2e8f0]">
          Execution input (JSON)
        </label>
        <textarea
          value={inputJson}
          onChange={(e) => setInputJson(e.target.value)}
          rows={4}
          className="w-full rounded-xl border bg-transparent px-4 py-3 font-mono text-xs text-[#e2e8f0] outline-none focus:border-[#60a5fa]"
          style={{ borderColor: "rgba(255,255,255,0.08)" }}
        />
        {parseError && <p className="mt-1 text-xs text-[#f87171]">{parseError}</p>}
      </div>

      <button
        onClick={handleExecute}
        disabled={executing}
        className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium text-white transition-all disabled:opacity-40"
        style={{
          background: "linear-gradient(135deg, #60a5fa, #a78bfa)",
          boxShadow: "0 0 16px rgba(96,165,250,0.25)",
        }}
      >
        <Play className="h-4 w-4" />
        {executing ? "Running..." : "Execute Chain"}
      </button>

      {execution && (
        <div
          className="rounded-xl border p-4 space-y-3"
          style={{ backgroundColor: "#141928", borderColor: "rgba(255,255,255,0.06)" }}
        >
          <div className="flex items-center gap-3">
            {statusIcon(execution.status)}
            <span className="text-sm font-medium text-[#e2e8f0]">Execution</span>
            <Badge label={execution.status} variant={statusVariant(execution.status) as "green" | "red" | "blue" | "gray"} />
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-[#475569]">ID:</span>{" "}
              <span className="font-mono text-[#94a3b8]">{execution.id.slice(0, 12)}...</span>
            </div>
            <div>
              <span className="text-[#475569]">Cost:</span>{" "}
              <span className="text-[#e2e8f0]">${execution.total_cost_usd.toFixed(4)}</span>
            </div>
            {execution.created_at && (
              <div>
                <span className="text-[#475569]">Started:</span>{" "}
                <span className="text-[#94a3b8]">{new Date(execution.created_at).toLocaleTimeString()}</span>
              </div>
            )}
            {execution.completed_at && (
              <div>
                <span className="text-[#475569]">Completed:</span>{" "}
                <span className="text-[#94a3b8]">{new Date(execution.completed_at).toLocaleTimeString()}</span>
              </div>
            )}
          </div>

          {execution.output_json && (
            <div>
              <p className="mb-1 text-xs text-[#475569]">Output:</p>
              <pre
                className="max-h-48 overflow-auto rounded-lg p-3 text-xs text-[#e2e8f0]"
                style={{ backgroundColor: "rgba(0,0,0,0.3)" }}
              >
                {typeof execution.output_json === "string"
                  ? execution.output_json
                  : JSON.stringify(execution.output_json, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
