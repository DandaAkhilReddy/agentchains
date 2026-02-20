import { Clock, ShieldCheck } from "lucide-react";
import { truncateId, relativeTime, formatUSD } from "../lib/format";
import type { Execution } from "../hooks/useActions";

/* ── Status styling ── */

const STATUS_STYLES: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  completed: {
    bg: "rgba(52,211,153,0.1)",
    text: "#34d399",
    border: "rgba(52,211,153,0.2)",
    glow: "0 0 8px rgba(52,211,153,0.08)",
  },
  failed: {
    bg: "rgba(248,113,113,0.1)",
    text: "#f87171",
    border: "rgba(248,113,113,0.2)",
    glow: "0 0 8px rgba(248,113,113,0.08)",
  },
  executing: {
    bg: "rgba(251,191,36,0.1)",
    text: "#fbbf24",
    border: "rgba(251,191,36,0.2)",
    glow: "0 0 8px rgba(251,191,36,0.08)",
  },
  pending: {
    bg: "rgba(96,165,250,0.1)",
    text: "#60a5fa",
    border: "rgba(96,165,250,0.2)",
    glow: "0 0 8px rgba(96,165,250,0.08)",
  },
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending;
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium"
      style={{
        backgroundColor: style.bg,
        color: style.text,
        border: `1px solid ${style.border}`,
        boxShadow: style.glow,
      }}
    >
      {status}
    </span>
  );
}

/* ── Component ── */

interface Props {
  executions: Execution[];
}

export default function ExecutionHistory({ executions }: Props) {
  if (executions.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-12"
        style={{
          backgroundColor: "rgba(20,25,40,0.5)",
          borderColor: "rgba(255,255,255,0.08)",
        }}
      >
        <div
          className="mb-3 rounded-2xl p-4"
          style={{
            backgroundColor: "rgba(96,165,250,0.08)",
            boxShadow: "0 0 24px rgba(96,165,250,0.1)",
          }}
        >
          <Clock className="h-8 w-8 text-[#60a5fa] animate-pulse" />
        </div>
        <p className="text-sm font-medium text-[#94a3b8]">
          No executions yet
        </p>
        <p className="mt-1 text-xs text-[#64748b]">
          Execute an action to see history here
        </p>
      </div>
    );
  }

  return (
    <div
      className="overflow-hidden rounded-2xl border"
      style={{
        backgroundColor: "#141928",
        borderColor: "rgba(96,165,250,0.12)",
      }}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr
              className="border-b text-left text-[11px] font-medium uppercase tracking-wider text-[#64748b]"
              style={{ borderColor: "rgba(255,255,255,0.06)" }}
            >
              <th className="px-5 py-3">ID</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Amount</th>
              <th className="px-5 py-3">Time</th>
              <th className="px-5 py-3">Proof</th>
            </tr>
          </thead>
          <tbody>
            {executions.map((exec) => (
              <tr
                key={exec.id}
                className="border-b transition-colors hover:bg-[rgba(96,165,250,0.04)]"
                style={{ borderColor: "rgba(255,255,255,0.04)" }}
              >
                {/* ID (truncated) */}
                <td className="px-5 py-3">
                  <span
                    className="font-mono text-xs text-[#94a3b8]"
                    title={exec.id}
                  >
                    {truncateId(exec.id)}
                  </span>
                </td>

                {/* Status badge */}
                <td className="px-5 py-3">
                  <StatusBadge status={exec.status} />
                </td>

                {/* Amount */}
                <td className="px-5 py-3">
                  <span className="font-mono text-xs font-semibold text-[#34d399]">
                    {formatUSD(exec.amount)}
                  </span>
                </td>

                {/* Time */}
                <td className="px-5 py-3">
                  <span className="flex items-center gap-1 text-xs text-[#64748b]">
                    <Clock className="h-3 w-3" />
                    {relativeTime(exec.created_at)}
                  </span>
                </td>

                {/* Proof verified */}
                <td className="px-5 py-3">
                  {exec.proof_verified ? (
                    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
                      style={{
                        backgroundColor: "rgba(52,211,153,0.1)",
                        color: "#34d399",
                        border: "1px solid rgba(52,211,153,0.2)",
                      }}
                    >
                      <ShieldCheck className="h-3 w-3" />
                      Verified
                    </span>
                  ) : (
                    <span className="text-[11px] text-[#64748b]">--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
