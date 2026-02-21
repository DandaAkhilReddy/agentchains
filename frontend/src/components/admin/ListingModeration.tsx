import { useState, useMemo } from "react";
import {
  Store,
  CheckCircle,
  XCircle,
  Eye,
  ExternalLink,
} from "lucide-react";
import Spinner from "../Spinner";
import EmptyState from "../EmptyState";
import { formatUSD, formatBytes } from "../../lib/format";

/**
 * Listing approval/rejection panel for platform administrators.
 *
 * Displays pending listings with content preview, allowing admins to
 * approve or reject each listing with an optional reason.
 */

export interface PendingListing {
  id: string;
  seller_id: string;
  seller_name: string;
  title: string;
  description: string;
  category: string;
  price_usdc: number;
  content_size: number;
  content_type: string;
  quality_score: number;
  tags: string[];
  created_at: string;
  status: "pending" | "approved" | "rejected";
}

interface ListingModerationProps {
  listings: PendingListing[];
  isLoading: boolean;
  onApprove: (listingId: string, notes?: string) => void;
  onReject: (listingId: string, reason: string) => void;
  onViewContent?: (listingId: string) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  web_search: "#60a5fa",
  code_analysis: "#a78bfa",
  document_summary: "#34d399",
  api_response: "#fbbf24",
  computation: "#f472b6",
};

export default function ListingModeration({
  listings,
  isLoading,
  onApprove,
  onReject,
  onViewContent,
}: ListingModerationProps) {
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [filterStatus, setFilterStatus] = useState<
    "all" | "pending" | "approved" | "rejected"
  >("pending");

  const filteredListings = useMemo(() => {
    if (filterStatus === "all") return listings;
    return listings.filter((l) => l.status === filterStatus);
  }, [listings, filterStatus]);

  const pendingCount = useMemo(
    () => listings.filter((l) => l.status === "pending").length,
    [listings],
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
        <Spinner label="Loading listings..." />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[rgba(52,211,153,0.1)]">
            <Store className="h-4 w-4 text-[#34d399]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[#e2e8f0]">
              Listing Moderation
            </h3>
            <p className="text-xs text-[#64748b]">
              {pendingCount} listing{pendingCount !== 1 ? "s" : ""} pending
              approval
            </p>
          </div>
        </div>

        {/* Status filter */}
        <div className="flex rounded-lg border border-[rgba(255,255,255,0.06)] bg-[#0d1220] p-0.5">
          {(["pending", "approved", "rejected", "all"] as const).map(
            (status) => (
              <button
                key={status}
                onClick={() => setFilterStatus(status)}
                className={`rounded-md px-3 py-1 text-[10px] font-medium uppercase tracking-wider transition-colors ${
                  filterStatus === status
                    ? "bg-[rgba(96,165,250,0.1)] text-[#60a5fa]"
                    : "text-[#64748b] hover:text-[#94a3b8]"
                }`}
              >
                {status}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Listings */}
      {filteredListings.length === 0 ? (
        <EmptyState
          message={
            filterStatus === "pending"
              ? "No listings pending approval."
              : "No listings match the selected filter."
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredListings.map((listing) => {
            const categoryColor =
              CATEGORY_COLORS[listing.category] ?? "#94a3b8";
            const isExpanded = previewId === listing.id;

            return (
              <div
                key={listing.id}
                className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] overflow-hidden"
              >
                {/* Main row */}
                <div className="flex items-start gap-4 p-4">
                  {/* Content info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className="inline-block rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                        style={{
                          backgroundColor: `${categoryColor}15`,
                          color: categoryColor,
                        }}
                      >
                        {listing.category.replace("_", " ")}
                      </span>
                      <span className="text-[10px] text-[#64748b]">
                        {formatBytes(listing.content_size)}
                      </span>
                      <span className="text-[10px] text-[#475569]">
                        {listing.content_type}
                      </span>
                    </div>

                    <h4 className="text-sm font-medium text-[#e2e8f0]">
                      {listing.title}
                    </h4>
                    <p className="mt-0.5 text-xs text-[#94a3b8] line-clamp-2">
                      {listing.description}
                    </p>

                    {/* Metadata row */}
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-[#64748b]">
                      <span>
                        Price:{" "}
                        <span className="text-[#34d399]">
                          {formatUSD(listing.price_usdc)}
                        </span>
                      </span>
                      <span>
                        Quality:{" "}
                        <span className="text-[#60a5fa]">
                          {Math.round(listing.quality_score * 100)}%
                        </span>
                      </span>
                      <span>
                        Seller:{" "}
                        <span className="text-[#94a3b8]">
                          {listing.seller_name}
                        </span>
                      </span>
                      <span>
                        {new Date(listing.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    {/* Tags */}
                    {listing.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {listing.tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded-full bg-[#1e293b] px-2 py-0.5 text-[10px] text-[#94a3b8]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-shrink-0 flex-col items-end gap-2">
                    {/* View content */}
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() =>
                          setPreviewId(isExpanded ? null : listing.id)
                        }
                        className="flex items-center gap-1 rounded-lg border border-[rgba(255,255,255,0.1)] px-2.5 py-1 text-[10px] text-[#94a3b8] transition-colors hover:text-[#e2e8f0]"
                      >
                        <Eye className="h-3 w-3" />
                        Preview
                      </button>
                      {onViewContent && (
                        <button
                          onClick={() => onViewContent(listing.id)}
                          className="rounded-lg border border-[rgba(255,255,255,0.1)] p-1 text-[#64748b] transition-colors hover:text-[#60a5fa]"
                          title="Open full content"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      )}
                    </div>

                    {/* Approve / Reject */}
                    {listing.status === "pending" && (
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => onApprove(listing.id)}
                          className="flex items-center gap-1 rounded-lg bg-[rgba(52,211,153,0.1)] px-3 py-1.5 text-xs font-medium text-[#34d399] transition-colors hover:bg-[rgba(52,211,153,0.2)]"
                        >
                          <CheckCircle className="h-3.5 w-3.5" />
                          Approve
                        </button>
                        <button
                          onClick={() => setRejectingId(listing.id)}
                          className="flex items-center gap-1 rounded-lg bg-[rgba(248,113,113,0.1)] px-3 py-1.5 text-xs font-medium text-[#f87171] transition-colors hover:bg-[rgba(248,113,113,0.2)]"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                          Reject
                        </button>
                      </div>
                    )}

                    {/* Status badge for non-pending */}
                    {listing.status !== "pending" && (
                      <span
                        className="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase"
                        style={{
                          backgroundColor:
                            listing.status === "approved"
                              ? "rgba(52,211,153,0.15)"
                              : "rgba(248,113,113,0.15)",
                          color:
                            listing.status === "approved"
                              ? "#34d399"
                              : "#f87171",
                        }}
                      >
                        {listing.status}
                      </span>
                    )}
                  </div>
                </div>

                {/* Reject reason input */}
                {rejectingId === listing.id && (
                  <div className="flex items-center gap-2 border-t border-[rgba(255,255,255,0.04)] bg-[rgba(248,113,113,0.03)] px-4 py-3">
                    <input
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Reason for rejection..."
                      autoFocus
                      className="flex-1 rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#0d1220] px-3 py-1.5 text-xs text-[#e2e8f0] placeholder-[#475569] outline-none focus:border-[#f87171]"
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleReject(listing.id);
                        if (e.key === "Escape") {
                          setRejectingId(null);
                          setRejectReason("");
                        }
                      }}
                    />
                    <button
                      onClick={() => handleReject(listing.id)}
                      disabled={!rejectReason.trim()}
                      className="rounded-lg bg-[#f87171] px-3 py-1.5 text-xs font-medium text-[#0a0e1a] transition-colors hover:bg-[#ef4444] disabled:opacity-50"
                    >
                      Confirm Reject
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

                {/* Expanded content preview */}
                {isExpanded && (
                  <div className="border-t border-[rgba(255,255,255,0.04)] bg-[#0d1220] px-6 py-4">
                    <p className="mb-2 text-[10px] uppercase tracking-wider text-[#64748b]">
                      Content Preview
                    </p>
                    <div className="rounded-lg bg-[#141928] p-4">
                      <p className="text-sm leading-relaxed text-[#94a3b8]">
                        {listing.description}
                      </p>
                      <div className="mt-3 flex gap-4 text-[10px] text-[#475569]">
                        <span>
                          Listing ID:{" "}
                          <span className="font-mono">{listing.id}</span>
                        </span>
                        <span>
                          Seller ID:{" "}
                          <span className="font-mono">
                            {listing.seller_id.slice(0, 12)}...
                          </span>
                        </span>
                      </div>
                    </div>
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
