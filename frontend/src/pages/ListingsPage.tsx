import { useState, useCallback } from "react";
import { useDiscover } from "../hooks/useDiscover";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import SearchInput from "../components/SearchInput";
import Badge, { categoryVariant } from "../components/Badge";
import QualityBar from "../components/QualityBar";
import { SkeletonCard } from "../components/Skeleton";
import EmptyState from "../components/EmptyState";
import { formatUSDC, relativeTime, formatBytes } from "../lib/format";
import { expressBuy } from "../lib/api";
import { Search, Code, FileText, Globe, Cpu, Zap } from "lucide-react";
import type { Category, Listing } from "../types/api";

const CATEGORY_ICONS: Record<string, typeof Search> = {
  web_search: Search,
  code_analysis: Code,
  document_summary: FileText,
  api_response: Globe,
  computation: Cpu,
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
  { value: "price_asc", label: "Price: Low -> High" },
  { value: "price_desc", label: "Price: High -> Low" },
  { value: "quality", label: "Highest Quality" },
] as const;

function ListingCard({ listing, onExpressBuy }: { listing: Listing; onExpressBuy: (id: string) => void }) {
  const catLabel = listing.category.replace(/_/g, " ");
  const CatIcon = CATEGORY_ICONS[listing.category] ?? Globe;

  return (
    <div className="group flex flex-col rounded-xl border border-zinc-800 bg-zinc-900 p-4 transition-all hover:border-zinc-700 hover:scale-[1.02] hover:shadow-lg hover:shadow-black/20">
      {/* Header */}
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-zinc-800 p-1.5">
            <CatIcon className="h-3.5 w-3.5 text-zinc-400" />
          </div>
          <h4 className="line-clamp-2 text-sm font-medium leading-tight">
            {listing.title}
          </h4>
        </div>
        <span
          className="flex-shrink-0 whitespace-nowrap rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-400"
          style={{ fontFamily: "var(--font-mono)" }}
        >
          {formatUSDC(listing.price_usdc)}
        </span>
      </div>

      {/* Category + seller */}
      <div className="mb-3 flex items-center gap-2">
        <Badge label={catLabel} variant={categoryVariant(listing.category)} />
        {listing.seller && (
          <span className="text-xs text-zinc-500">
            by {listing.seller.name}
          </span>
        )}
      </div>

      {/* Description */}
      {listing.description && (
        <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-zinc-500">
          {listing.description}
        </p>
      )}

      {/* Quality + meta */}
      <div className="mt-auto flex items-center justify-between pt-2">
        <QualityBar score={listing.quality_score} />
        <div className="flex items-center gap-3 text-[11px] text-zinc-600">
          <span>{formatBytes(listing.content_size)}</span>
          <span>{relativeTime(listing.freshness_at)}</span>
        </div>
      </div>

      {/* Tags */}
      {listing.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {listing.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500"
            >
              {tag}
            </span>
          ))}
          {listing.tags.length > 3 && (
            <span className="text-[10px] text-zinc-600">
              +{listing.tags.length - 3}
            </span>
          )}
        </div>
      )}

      {/* Express Buy button - appears on hover */}
      <button
        onClick={() => onExpressBuy(listing.id)}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white opacity-0 transition-all group-hover:opacity-100 hover:bg-emerald-500"
      >
        <Zap className="h-3.5 w-3.5" />
        Express Buy
      </button>
    </div>
  );
}

export default function ListingsPage() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState<Category | "">("");
  const [sortBy, setSortBy] = useState<"freshness" | "price_asc" | "price_desc" | "quality">("freshness");
  const [page, setPage] = useState(1);
  const { token } = useAuth();
  const { toast } = useToast();

  const handleSearch = useCallback((val: string) => {
    setQ(val);
    setPage(1);
  }, []);

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
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput
          value={q}
          onChange={handleSearch}
          placeholder="Search listings..."
        />
        <select
          value={category}
          onChange={(e) => { setCategory(e.target.value as Category | ""); setPage(1); }}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none"
        >
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white outline-none"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        {data && (
          <span className="ml-auto text-sm text-zinc-500">
            {data.total} result{data.total !== 1 && "s"}
          </span>
        )}
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : !data || data.results.length === 0 ? (
        <EmptyState message="No listings found" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.results.map((listing) => (
            <ListingCard
              key={listing.id}
              listing={listing}
              onExpressBuy={handleExpressBuy}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {data && data.total > 12 && (
        <div className="flex items-center justify-end gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 disabled:opacity-30"
          >
            Prev
          </button>
          <span className="text-sm text-zinc-500">Page {page}</span>
          <button
            disabled={page * 12 >= data.total}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm text-zinc-400 transition-colors hover:bg-zinc-800 disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
