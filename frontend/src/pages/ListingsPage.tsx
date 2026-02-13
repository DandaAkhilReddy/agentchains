import { useState, useCallback } from "react";
import { useDiscover } from "../hooks/useDiscover";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import SearchInput from "../components/SearchInput";
import Badge, { categoryVariant } from "../components/Badge";
import QualityBar from "../components/QualityBar";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import { formatUSD, relativeTime, formatBytes } from "../lib/format";
import { expressBuy } from "../lib/api";
import {
  Search,
  Code,
  FileText,
  Globe,
  Cpu,
  Zap,
  Store,
  SlidersHorizontal,
  Eye,
  Clock,
  HardDrive,
  ShieldCheck,
  PackageOpen,
  ArrowDownUp,
  ChevronDown,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import type { Category, Listing } from "../types/api";

/* ────────────────────── Constants ────────────────────── */

const CATEGORY_ICONS: Record<string, typeof Search> = {
  web_search: Search,
  code_analysis: Code,
  document_summary: FileText,
  api_response: Globe,
  computation: Cpu,
};

const CATEGORY_ACCENT: Record<string, string> = {
  web_search: "#60a5fa",
  code_analysis: "#a78bfa",
  document_summary: "#34d399",
  api_response: "#fbbf24",
  computation: "#22d3ee",
};

const CATEGORY_GLOW: Record<string, string> = {
  web_search: "rgba(96,165,250,0.25)",
  code_analysis: "rgba(167,139,250,0.25)",
  document_summary: "rgba(52,211,153,0.25)",
  api_response: "rgba(251,191,36,0.25)",
  computation: "rgba(34,211,238,0.25)",
};

const CATEGORIES: { value: Category | ""; label: string }[] = [
  { value: "", label: "All Categories" },
  { value: "web_search", label: "Web Search" },
  { value: "code_analysis", label: "Code Analysis" },
  { value: "document_summary", label: "Doc Summary" },
  { value: "api_response", label: "API Response" },
  { value: "computation", label: "Computation" },
];

const SORTS = [
  { value: "freshness", label: "Freshest" },
  { value: "price_asc", label: "Price: Low \u2192 High" },
  { value: "price_desc", label: "Price: High \u2192 Low" },
  { value: "quality", label: "Highest Quality" },
] as const;

/* ────────────────────── Freshness Badge ────────────────────── */

function FreshnessBadge({ iso }: { iso: string }) {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = diff / (1000 * 60 * 60);
  const label = relativeTime(iso);

  let color: string;
  let bg: string;
  let glow: string;
  if (hours < 1) {
    color = "#34d399";
    bg = "rgba(52,211,153,0.1)";
    glow = "0 0 6px rgba(52,211,153,0.2)";
  } else if (hours < 24) {
    color = "#60a5fa";
    bg = "rgba(96,165,250,0.1)";
    glow = "0 0 6px rgba(96,165,250,0.15)";
  } else {
    color = "#94a3b8";
    bg = "rgba(148,163,184,0.08)";
    glow = "none";
  }

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{ color, backgroundColor: bg, boxShadow: glow }}
    >
      <Clock className="h-2.5 w-2.5" />
      {label}
    </span>
  );
}

/* ────────────────────── Listing Card ────────────────────── */

function ListingCard({
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

/* ────────────────────── Skeleton Card (dark) ────────────────────── */

function DarkSkeletonCard() {
  return (
    <div
      className="overflow-hidden rounded-2xl border"
      style={{
        backgroundColor: "#141928",
        borderColor: "rgba(255,255,255,0.06)",
      }}
    >
      {/* Accent bar skeleton */}
      <div className="h-[3px] w-full animate-pulse" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />

      <div className="space-y-4 p-5">
        {/* Icon + title */}
        <div className="flex items-start gap-3">
          <div className="h-8 w-8 animate-pulse rounded-xl" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-3/4 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
            <div className="h-3 w-1/2 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          </div>
        </div>

        {/* Price line */}
        <div className="flex items-center justify-between">
          <div className="h-5 w-20 animate-pulse rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
          <div className="h-6 w-16 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <div className="h-3 w-full animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-3 w-2/3 animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
        </div>

        {/* Quality bar */}
        <div className="h-2 w-full animate-pulse rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />

        {/* Meta row */}
        <div className="flex gap-3">
          <div className="h-4 w-14 animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-4 w-14 animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-4 w-14 animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
        </div>

        {/* Tags */}
        <div className="flex gap-1.5">
          <div className="h-5 w-12 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-5 w-14 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-5 w-10 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
        </div>
      </div>
    </div>
  );
}

/* ────────────────────── Empty State (dark) ────────────────────── */

function DarkEmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-2xl border border-dashed py-20"
      style={{
        backgroundColor: "rgba(20,25,40,0.5)",
        borderColor: "rgba(255,255,255,0.08)",
      }}
    >
      <div
        className="mb-4 rounded-2xl p-5"
        style={{
          backgroundColor: "rgba(96,165,250,0.08)",
          boxShadow: "0 0 24px rgba(96,165,250,0.1)",
        }}
      >
        <PackageOpen className="h-10 w-10 text-[#60a5fa] animate-pulse" />
      </div>
      <p className="text-base font-medium text-[#94a3b8]">No listings found</p>
      <p className="mt-1 text-sm text-[#64748b]">
        Try adjusting your filters or search query
      </p>
    </div>
  );
}

/* ────────────────────── Auth Gate ────────────────────── */

function AuthGateBanner() {
  return (
    <div
      className="flex items-center gap-3 rounded-xl border px-4 py-3"
      style={{
        backgroundColor: "rgba(251,191,36,0.06)",
        borderColor: "rgba(251,191,36,0.15)",
      }}
    >
      <ShieldCheck className="h-4 w-4 flex-shrink-0 text-[#fbbf24]" />
      <p className="text-xs text-[#fbbf24]">
        Connect your agent JWT in the Transactions tab to enable Express Buy
      </p>
    </div>
  );
}

/* ────────────────────── Main Page ────────────────────── */

export default function ListingsPage() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [sortBy, setSortBy] = useState<
    "freshness" | "price_asc" | "price_desc" | "quality"
  >("freshness");
  const [page, setPage] = useState(1);
  const { token } = useAuth();
  const { toast } = useToast();

  const handleSearch = useCallback(
    (val: string) => {
      setQ(val);
      setPage(1);
    },
    [],
  );

  const { data, isLoading } = useDiscover({
    q: q || undefined,
    category: category || undefined,
    sort_by: sortBy,
    page,
    page_size: 12,
  });

  const handleExpressBuy = async (listingId: string) => {
    if (!token) {
      toast("Connect your agent JWT first (Transactions tab)", "error");
      return;
    }
    try {
      const result = await expressBuy(token, listingId);
      toast(
        `Purchased! Delivered in ${result.delivery_ms}ms ${result.cache_hit ? "(cache hit)" : ""}`,
        "success",
      );
    } catch (err) {
      toast((err as Error).message, "error");
    }
  };

  return (
    <div className="space-y-6">
      {/* ── Page Header ── */}
      <PageHeader
        title="Marketplace"
        subtitle="Discover and purchase cached computation results"
        icon={Store}
        actions={
          data ? (
            <div className="flex items-center gap-2">
              <span
                className="flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
                style={{
                  backgroundColor: "rgba(96,165,250,0.1)",
                  color: "#60a5fa",
                  border: "1px solid rgba(96,165,250,0.2)",
                }}
              >
                <TrendingUp className="h-3 w-3" />
                {data.total} listing{data.total !== 1 ? "s" : ""}
              </span>
            </div>
          ) : null
        }
      />

      {/* ── Auth Gate Banner ── */}
      {!token && <AuthGateBanner />}

      {/* ── Filter / Sort Bar ── */}
      <div
        className="flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center"
        style={{
          backgroundColor: "#141928",
          borderColor: "rgba(255,255,255,0.06)",
        }}
      >
        {/* Search */}
        <div className="flex-1 sm:max-w-xs">
          <SearchInput
            value={q}
            onChange={handleSearch}
            placeholder="Search listings..."
          />
        </div>

        {/* Category select */}
        <div className="relative">
          <SlidersHorizontal className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value as Category | "");
              setPage(1);
            }}
            className="appearance-none rounded-xl border py-2 pl-9 pr-8 text-sm outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)]"
            style={{
              backgroundColor: "#1a2035",
              borderColor: "rgba(255,255,255,0.06)",
              color: "#e2e8f0",
            }}
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
        </div>

        {/* Sort select */}
        <div className="relative">
          <ArrowDownUp className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
            className="appearance-none rounded-xl border py-2 pl-9 pr-8 text-sm outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)]"
            style={{
              backgroundColor: "#1a2035",
              borderColor: "rgba(255,255,255,0.06)",
              color: "#e2e8f0",
            }}
          >
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
        </div>

        {/* Results count (desktop) */}
        {data && (
          <div className="hidden sm:ml-auto sm:flex sm:items-center sm:gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-[#a78bfa]" />
            <span className="text-xs text-[#94a3b8]">
              {data.total} result{data.total !== 1 ? "s" : ""}
            </span>
          </div>
        )}
      </div>

      {/* ── Listing Grid ── */}
      {isLoading ? (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <DarkSkeletonCard key={i} />
          ))}
        </div>
      ) : !data || data.results.length === 0 ? (
        <DarkEmptyState />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {data.results.map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onExpressBuy={handleExpressBuy}
            />
          ))}
        </div>
      )}

      {/* ── Pagination ── */}
      {data && data.total > 12 && (
        <Pagination
          page={page}
          totalPages={Math.ceil(data.total / 12)}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
