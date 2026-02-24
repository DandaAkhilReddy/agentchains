import { useState, useCallback } from "react";
import { useDiscover } from "../hooks/useDiscover";
import { useAuth } from "../hooks/useAuth";
import { useToast } from "../components/Toast";
import SearchInput from "../components/SearchInput";
import PageHeader from "../components/PageHeader";
import Pagination from "../components/Pagination";
import { expressBuy } from "../lib/api";
import {
  ListingCard,
  DarkSkeletonCard,
  DarkEmptyState,
  AuthGateBanner,
} from "../components/listings";
import {
  Store,
  SlidersHorizontal,
  ArrowDownUp,
  ChevronDown,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import type { Category } from "../types/api";

/* ────────────────────── Constants ────────────────────── */

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
