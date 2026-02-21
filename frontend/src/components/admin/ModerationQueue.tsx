import { useState, useMemo } from "react";
import { Shield, CheckCircle, XCircle, Filter } from "lucide-react";
import Spinner from "../Spinner";
import EmptyState from "../EmptyState";

/**
 * Content moderation queue for platform administrators.
 *
 * Displays a list of items pending review with approve/reject actions
 * and filtering by content type.
 */

export type ModerationItemType = "listing" | "agent" | "content" | "payout";
export type ModerationItemStatus = "pending" | "approved" | "rejected";

export interface ModerationItem {
  id: string;
  type: ModerationItemType;
  title: string;
  description: string;
  submitted_by: string;
  submitted_at: string;
  status: ModerationItemStatus;
  metadata?: Record<string, unknown>;
}

interface ModerationQueueProps {
  items: ModerationItem[];
  isLoading: boolean;
  onApprove: (id: string, notes?: string) => void;
  onReject: (id: string, reason: string) => void;
}

const TYPE_LABELS: Record<ModerationItemType, string> = {
  listing: "Listing",
  agent: "Agent",
  content: "Content",
  payout: "Payout",
};

const TYPE_COLORS: Record<ModerationItemType, string> = {
  listing: "#60a5fa",
  agent: "#a78bfa",
  content: "#34d399",
  payout: "#fbbf24",
};

const STATUS_CONFIG: Record<
  ModerationItemStatus,
  { label: string; color: string }
> = {
  pending: { label: "Pending", color: "#fbbf24" },
  approved: { label: "Approved", color: "#34d399" },
  rejected: { label: "Rejected", color: "#f87171" },
};

export default function ModerationQueue({
  items,
  isLoading,
  onApprove,
  onReject,
}: ModerationQueueProps) {
  const [filterType, setFilterType] = useState<ModerationItemType | "all">("all");
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const filteredItems = useMemo(() => {
    if (filterType === "all") return items;
    return items.filter((item) => item.type === filterType);
  }, [items, filterType]);

  const pendingCount = useMemo(
    () => items.filter((item) => item.status === "pending").length,
    [items],
  );

  const handleReject = (id: string) => {
    if (!rejectReason.trim()) return;
    onReject(id, rejectReason.trim());
    setRejectingId(null);
    setRejectReason("");
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 bg-[#141928] rounded-2xl border border-[rgba(255,255,255,0.06)]">
        <Spinner label="Loading moderation queue..." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(96,165,250,0.1)]">
            <Shield className="h-4 w-4 text-[#60a5fa]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#e2e8f0]">
              Moderation Queue
            </h3>
            <p className="text-xs text-[#64748b]">
              {pendingCount} item{pendingCount !== 1 ? "s" : ""} pending review
            </p>
          </div>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5 text-[#64748b]" />
          <select
            value={filterType}
            onChange={(e) =>
              setFilterType(e.target.value as ModerationItemType | "all")
            }
            className="rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-1.5 text-xs text-[#e2e8f0] outline-none focus:border-[#60a5fa]"
          >
            <option value="all">All Types</option>
            <option value="listing">Listings</option>
            <option value="agent">Agents</option>
            <option value="content">Content</option>
            <option value="payout">Payouts</option>
          </select>
        </div>
      </div>

      {/* Queue list */}
      {filteredItems.length === 0 ? (
        <EmptyState message="No items in the moderation queue." />
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => {
            const statusConfig = STATUS_CONFIG[item.status];
            const typeColor = TYPE_COLORS[item.type];

            return (
              <div
                key={item.id}
                className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4 transition-colors hover:bg-[rgba(96,165,250,0.02)]"
              >
                <div className="flex items-start justify-between gap-4">
                  {/* Left: info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                        style={{
                          backgroundColor: `${typeColor}15`,
                          color: typeColor,
                        }}
                      >
                        {TYPE_LABELS[item.type]}
                      </span>
                      <span
                        className="inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
                        style={{
                          backgroundColor: `${statusConfig.color}15`,
                          color: statusConfig.color,
                        }}
                      >
                        {statusConfig.label}
                      </span>
                    </div>
                    <h4 className="text-sm font-medium text-[#e2e8f0] truncate">
                      {item.title}
                    </h4>
                    <p className="mt-0.5 text-xs text-[#94a3b8] line-clamp-2">
                      {item.description}
                    </p>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-[#64748b]">
                      <span>By: {item.submitted_by}</span>
                      <span>{new Date(item.submitted_at).toLocaleString()}</span>
                      <span className="font-mono text-[#475569]">
                        {item.id.slice(0, 8)}
                      </span>
                    </div>
                  </div>

                  {/* Right: actions */}
                  {item.status === "pending" && (
                    <div className="flex flex-shrink-0 items-center gap-2">
                      <button
                        onClick={() => onApprove(item.id)}
                        className="flex items-center gap-1.5 rounded-lg bg-[rgba(52,211,153,0.1)] px-3 py-1.5 text-xs font-medium text-[#34d399] transition-colors hover:bg-[rgba(52,211,153,0.2)]"
                        title="Approve"
                      >
                        <CheckCircle className="h-3.5 w-3.5" />
                        Approve
                      </button>
                      <button
                        onClick={() => setRejectingId(item.id)}
                        className="flex items-center gap-1.5 rounded-lg bg-[rgba(248,113,113,0.1)] px-3 py-1.5 text-xs font-medium text-[#f87171] transition-colors hover:bg-[rgba(248,113,113,0.2)]"
                        title="Reject"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        Reject
                      </button>
                    </div>
                  )}
                </div>

                {/* Reject reason input */}
                {rejectingId === item.id && (
                  <div className="mt-3 flex items-center gap-2 border-t border-[rgba(255,255,255,0.04)] pt-3">
                    <input
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Reason for rejection..."
                      autoFocus
                      className="flex-1 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-1.5 text-xs text-[#e2e8f0] placeholder-[#475569] outline-none focus:border-[#f87171]"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleReject(item.id);
                        if (e.key === "Escape") {
                          setRejectingId(null);
                          setRejectReason("");
                        }
                      }}
                    />
                    <button
                      onClick={() => handleReject(item.id)}
                      disabled={!rejectReason.trim()}
                      className="rounded-lg bg-[#f87171] px-3 py-1.5 text-xs font-medium text-[#0a0e1a] transition-colors hover:bg-[#ef4444] disabled:opacity-50"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => {
                        setRejectingId(null);
                        setRejectReason("");
                      }}
                      className="rounded-lg border border-[rgba(255,255,255,0.1)] px-3 py-1.5 text-xs text-[#94a3b8] transition-colors hover:text-[#e2e8f0]"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
