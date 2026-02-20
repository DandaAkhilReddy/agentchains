import { useState } from "react";
import { Play, ShieldCheck, AlertTriangle, Loader2 } from "lucide-react";

interface Props {
  actionId: string;
  onExecute: (params: Record<string, unknown>, consent: boolean) => void;
  isLoading?: boolean;
}

export default function ExecutionForm({
  actionId,
  onExecute,
  isLoading = false,
}: Props) {
  const [rawParams, setRawParams] = useState("{}");
  const [consent, setConsent] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setParseError(null);

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(rawParams);
    } catch {
      setParseError("Invalid JSON. Please check your parameters.");
      return;
    }

    if (!consent) return;
    onExecute(parsed, consent);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border p-5 space-y-4"
      style={{
        backgroundColor: "#141928",
        borderColor: "rgba(96,165,250,0.12)",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="rounded-xl bg-[rgba(96,165,250,0.1)] p-2.5 shadow-[0_0_12px_rgba(96,165,250,0.15)]">
          <Play className="h-4 w-4 text-[#60a5fa]" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[#e2e8f0]">
            Execute Action
          </h3>
          <p className="text-[11px] text-[#64748b] font-mono">{actionId}</p>
        </div>
      </div>

      {/* Parameters textarea */}
      <div>
        <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-[#64748b]">
          Parameters (JSON)
        </label>
        <textarea
          value={rawParams}
          onChange={(e) => {
            setRawParams(e.target.value);
            setParseError(null);
          }}
          rows={6}
          spellCheck={false}
          className="w-full rounded-xl border px-4 py-3 text-sm font-mono outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)] resize-y"
          style={{
            backgroundColor: "#1a2035",
            borderColor: "rgba(255,255,255,0.06)",
            color: "#e2e8f0",
          }}
          placeholder='{ "key": "value" }'
        />
        {parseError && (
          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-[#f87171]">
            <AlertTriangle className="h-3 w-3" />
            {parseError}
          </div>
        )}
      </div>

      {/* Consent checkbox */}
      <label
        className="flex items-start gap-3 rounded-xl border px-4 py-3 cursor-pointer transition-all duration-200 hover:border-[rgba(96,165,250,0.3)]"
        style={{
          backgroundColor: consent
            ? "rgba(52,211,153,0.06)"
            : "rgba(255,255,255,0.02)",
          borderColor: consent
            ? "rgba(52,211,153,0.2)"
            : "rgba(255,255,255,0.06)",
        }}
      >
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded accent-[#34d399]"
        />
        <div>
          <span className="flex items-center gap-1.5 text-sm font-medium text-[#e2e8f0]">
            <ShieldCheck className="h-3.5 w-3.5 text-[#34d399]" />
            I consent to this execution
          </span>
          <p className="mt-0.5 text-[11px] text-[#64748b] leading-relaxed">
            By checking this box, you confirm that you authorize the execution
            of this action with the provided parameters. Charges will apply.
          </p>
        </div>
      </label>

      {/* Submit */}
      <button
        type="submit"
        disabled={!consent || isLoading}
        className="flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: consent
            ? "linear-gradient(135deg, #60a5fa, #34d399)"
            : "rgba(255,255,255,0.06)",
          boxShadow: consent
            ? "0 0 16px rgba(96,165,250,0.2)"
            : "none",
        }}
      >
        {isLoading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            Executing...
          </>
        ) : (
          <>
            <Play className="h-4 w-4" />
            Execute Action
          </>
        )}
      </button>
    </form>
  );
}
