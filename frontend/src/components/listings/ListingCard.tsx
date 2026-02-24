import {
  Globe,
  Eye,
  HardDrive,
  ShieldCheck,
  Zap,
} from "lucide-react";
import Badge, { categoryVariant } from "../Badge";
import QualityBar from "../QualityBar";
import { formatUSD, formatBytes } from "../../lib/format";
import FreshnessBadge from "./FreshnessBadge";
import { CATEGORY_ICONS, CATEGORY_ACCENT, CATEGORY_GLOW } from "./constants";
import type { Listing } from "../../types/api";

export default function ListingCard({
  listing,
  onExpressBuy,
}: {
  listing: Listing;
  onExpressBuy: (id: string) => void;
}) {
  const catLabel = listing.category.replace(/_/g, " ");
  const CatIcon = CATEGORY_ICONS[listing.category] ?? Globe;
  const accentColor = CATEGORY_ACCENT[listing.category] ?? "#60a5fa";
  const glowColor = CATEGORY_GLOW[listing.category] ?? "rgba(96,165,250,0.25)";
  const pct = Math.round(listing.quality_score * 100);

  return (
    <div
      className="group relative flex flex-col overflow-hidden rounded-2xl border transition-all duration-300 hover:-translate-y-1"
      style={{
        backgroundColor: "#141928",
        borderColor: "rgba(255,255,255,0.06)",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = accentColor;
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 8px 32px ${glowColor}, 0 0 0 1px ${accentColor}40`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.06)";
        (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
      }}
    >
      {/* Top accent bar */}
      <div
        className="h-[3px] w-full"
        style={{
          background: `linear-gradient(90deg, ${accentColor}, ${accentColor}80, transparent)`,
        }}
      />

      {/* Card content */}
      <div className="flex flex-1 flex-col p-5">
        {/* Category icon + Title row */}
        <div className="mb-3 flex items-start gap-3">
          <div
            className="flex-shrink-0 rounded-xl p-2"
            style={{
              backgroundColor: `${accentColor}15`,
              boxShadow: `0 0 12px ${accentColor}20`,
            }}
          >
            <CatIcon className="h-4 w-4" style={{ color: accentColor }} />
          </div>
          <div className="min-w-0 flex-1">
            <h4 className="line-clamp-2 text-sm font-semibold leading-snug text-[#e2e8f0] group-hover:text-white transition-colors">
              {listing.title}
            </h4>
          </div>
        </div>

        {/* Price + Category */}
        <div className="mb-3 flex items-center justify-between">
          <Badge label={catLabel} variant={categoryVariant(listing.category)} />
          <span
            className="text-lg font-bold font-mono tracking-tight text-[#34d399]"
            style={{
              textShadow: "0 0 12px rgba(52,211,153,0.3)",
            }}
          >
            {formatUSD(listing.price_usdc)}
          </span>
        </div>

        {/* Seller */}
        {listing.seller && (
          <div className="mb-3 flex items-center gap-2">
            <div
              className="flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold"
              style={{
                backgroundColor: `${accentColor}20`,
                color: accentColor,
              }}
            >
              {listing.seller.name.charAt(0).toUpperCase()}
            </div>
            <span className="text-xs text-[#94a3b8]">
              {listing.seller.name}
            </span>
            {listing.seller.reputation_score !== null && (
              <span className="ml-auto flex items-center gap-0.5 text-[10px] text-[#64748b]">
                <ShieldCheck className="h-3 w-3 text-[#34d399]" />
                {Math.round(listing.seller.reputation_score * 100)}%
              </span>
            )}
          </div>
        )}

        {/* Description */}
        {listing.description && (
          <p className="mb-4 line-clamp-2 text-xs leading-relaxed text-[#64748b]">
            {listing.description}
          </p>
        )}

        {/* Quality bar */}
        <div className="mb-3">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[10px] font-medium uppercase tracking-wider text-[#64748b]">
              Quality
            </span>
            <span
              className="text-[10px] font-bold"
              style={{
                color:
                  pct >= 70
                    ? "#34d399"
                    : pct >= 40
                      ? "#fbbf24"
                      : "#f87171",
              }}
            >
              {pct}%
            </span>
          </div>
          <QualityBar score={listing.quality_score} />
        </div>

        {/* Metadata row */}
        <div className="mb-3 flex items-center gap-3 text-[10px] text-[#64748b]">
          <span className="flex items-center gap-1">
            <HardDrive className="h-3 w-3" />
            {formatBytes(listing.content_size)}
          </span>
          <FreshnessBadge iso={listing.freshness_at} />
          <span className="ml-auto flex items-center gap-1">
            <Eye className="h-3 w-3" />
            {listing.access_count}
          </span>
        </div>

        {/* Tags */}
        {listing.tags.length > 0 && (
          <div className="mb-4 flex flex-wrap gap-1.5">
            {listing.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="rounded-md px-2 py-0.5 text-[10px] font-medium text-[#94a3b8] transition-colors hover:text-[#e2e8f0]"
                style={{
                  backgroundColor: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.06)",
                }}
              >
                {tag}
              </span>
            ))}
            {listing.tags.length > 3 && (
              <span className="rounded-md px-1.5 py-0.5 text-[10px] text-[#64748b]" style={{ backgroundColor: "rgba(255,255,255,0.03)" }}>
                +{listing.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Spacer pushes button to bottom */}
        <div className="flex-1" />

        {/* Express Buy button */}
        <button
          onClick={() => onExpressBuy(listing.id)}
          className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white opacity-0 transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0 translate-y-2"
          style={{
            background: "linear-gradient(135deg, #60a5fa, #34d399)",
            boxShadow: "0 0 0px rgba(96,165,250,0)",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.boxShadow =
              "0 0 24px rgba(96,165,250,0.35), 0 0 48px rgba(52,211,153,0.2)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.boxShadow =
              "0 0 0px rgba(96,165,250,0)";
          }}
        >
          <Zap className="h-4 w-4" />
          Express Buy
        </button>
      </div>
    </div>
  );
}
