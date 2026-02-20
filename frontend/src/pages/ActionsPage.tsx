import { useState, useCallback } from "react";
import {
  Zap,
  SlidersHorizontal,
  ChevronDown,
  DollarSign,
  PackageOpen,
  History,
  X,
} from "lucide-react";
import PageHeader from "../components/PageHeader";
import SearchInput from "../components/SearchInput";
import ActionCard from "../components/ActionCard";
import ExecutionForm from "../components/ExecutionForm";
import ExecutionHistory from "../components/ExecutionHistory";
import Pagination from "../components/Pagination";
import Badge from "../components/Badge";
import { useActions, useExecuteAction, useExecutions } from "../hooks/useActions";
import { useToast } from "../components/Toast";

/* ── Constants ── */

const CATEGORIES = [
  { value: "", label: "All Categories" },
  { value: "web_automation", label: "Web Automation" },
  { value: "data_extraction", label: "Data Extraction" },
  { value: "ai_inference", label: "AI Inference" },
  { value: "file_processing", label: "File Processing" },
  { value: "api_integration", label: "API Integration" },
] as const;

const MAX_PRICES = [
  { value: 0, label: "Any Price" },
  { value: 0.1, label: "Under $0.10" },
  { value: 0.5, label: "Under $0.50" },
  { value: 1, label: "Under $1.00" },
  { value: 5, label: "Under $5.00" },
] as const;

/* ── Skeleton Card ── */

function SkeletonCard() {
  return (
    <div
      className="overflow-hidden rounded-2xl border"
      style={{
        backgroundColor: "#141928",
        borderColor: "rgba(96,165,250,0.12)",
      }}
    >
      <div className="h-[3px] w-full animate-pulse" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
      <div className="space-y-4 p-5">
        <div className="flex items-start gap-3">
          <div className="h-9 w-9 animate-pulse rounded-xl" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-3/4 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
            <div className="h-3 w-1/2 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          </div>
        </div>
        <div className="space-y-1.5">
          <div className="h-3 w-full animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-3 w-2/3 animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
        </div>
        <div className="flex items-center justify-between">
          <div className="h-6 w-16 animate-pulse rounded-md" style={{ backgroundColor: "rgba(255,255,255,0.04)" }} />
          <div className="h-4 w-12 animate-pulse rounded" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
        </div>
        <div className="flex gap-1.5">
          <div className="h-5 w-12 animate-pulse rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-5 w-14 animate-pulse rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
          <div className="h-5 w-10 animate-pulse rounded-full" style={{ backgroundColor: "rgba(255,255,255,0.03)" }} />
        </div>
      </div>
    </div>
  );
}

/* ── Empty State ── */

function EmptyState() {
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
      <p className="text-base font-medium text-[#94a3b8]">No actions found</p>
      <p className="mt-1 text-sm text-[#64748b]">
        Try adjusting your filters or search query
      </p>
    </div>
  );
}

/* ── Main Page ── */

export default function ActionsPage() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [maxPrice, setMaxPrice] = useState(0);
  const [page, setPage] = useState(1);
  const [execPage, setExecPage] = useState(1);
  const [selectedActionId, setSelectedActionId] = useState<string | null>(null);
  const { toast } = useToast();

  const handleSearch = useCallback((val: string) => {
    setQ(val);
    setPage(1);
  }, []);

  /* Data hooks */
  const { data, isLoading } = useActions(
    q || undefined,
    category || undefined,
    maxPrice || undefined,
    page,
  );

  const executeMutation = useExecuteAction();
  const { data: execData } = useExecutions(execPage);

  /* Handlers */
  const handleOpenExecutePanel = (actionId: string) => {
    setSelectedActionId(actionId);
  };

  const handleExecute = (params: Record<string, unknown>, consent: boolean) => {
    if (!selectedActionId) return;

    executeMutation.mutate(
      {
        actionId: selectedActionId,
        payload: { parameters: params, consent },
      },
      {
        onSuccess: (result) => {
          toast(
            `Execution started! ID: ${result.execution_id}`,
            "success",
          );
          setSelectedActionId(null);
        },
        onError: (err) => {
          toast((err as Error).message, "error");
        },
      },
    );
  };

  const totalPages = data ? Math.ceil(data.total / 12) : 0;
  const execTotalPages = execData ? Math.ceil(execData.total / 20) : 0;

  return (
    <div className="space-y-6">
      {/* ── Page Header ── */}
      <PageHeader
        title="WebMCP Actions"
        subtitle="Discover and execute WebMCP-powered actions across the agent network"
        icon={Zap}
        actions={
          data ? (
            <div className="flex items-center gap-2">
              <Badge
                label={`${data.total} action${data.total !== 1 ? "s" : ""}`}
                variant="blue"
              />
            </div>
          ) : null
        }
      />

      {/* ── Filter Bar ── */}
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
            placeholder="Search actions..."
          />
        </div>

        {/* Category select */}
        <div className="relative">
          <SlidersHorizontal className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
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

        {/* Price filter */}
        <div className="relative">
          <DollarSign className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
          <select
            value={maxPrice}
            onChange={(e) => {
              setMaxPrice(Number(e.target.value));
              setPage(1);
            }}
            className="appearance-none rounded-xl border py-2 pl-9 pr-8 text-sm outline-none transition-all duration-200 focus:border-[rgba(96,165,250,0.5)] focus:shadow-[0_0_0_3px_rgba(96,165,250,0.1)]"
            style={{
              backgroundColor: "#1a2035",
              borderColor: "rgba(255,255,255,0.06)",
              color: "#e2e8f0",
            }}
          >
            {MAX_PRICES.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#64748b]" />
        </div>
      </div>

      {/* ── Action Grid + Execution Form Side Panel ── */}
      <div className="flex gap-6">
        {/* Grid */}
        <div className="flex-1 min-w-0">
          {isLoading ? (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : !data || data.actions.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {data.actions.map((action) => (
                <ActionCard
                  key={action.id}
                  action={action}
                  onExecute={handleOpenExecutePanel}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <Pagination
              page={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          )}
        </div>

        {/* Execution Form Panel (slides in when action selected) */}
        {selectedActionId && (
          <div className="hidden lg:block w-[380px] flex-shrink-0">
            <div className="sticky top-6 space-y-3">
              {/* Close button */}
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wider text-[#64748b]">
                  Execution Panel
                </span>
                <button
                  onClick={() => setSelectedActionId(null)}
                  className="flex h-7 w-7 items-center justify-center rounded-lg border transition-all duration-200 hover:bg-[rgba(248,113,113,0.1)] hover:border-[rgba(248,113,113,0.3)]"
                  style={{
                    backgroundColor: "rgba(255,255,255,0.03)",
                    borderColor: "rgba(255,255,255,0.06)",
                  }}
                >
                  <X className="h-3.5 w-3.5 text-[#94a3b8]" />
                </button>
              </div>

              <ExecutionForm
                actionId={selectedActionId}
                onExecute={handleExecute}
                isLoading={executeMutation.isPending}
              />
            </div>
          </div>
        )}
      </div>

      {/* ── Mobile Execution Form (shown below grid on small screens) ── */}
      {selectedActionId && (
        <div className="lg:hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium uppercase tracking-wider text-[#64748b]">
              Execution Panel
            </span>
            <button
              onClick={() => setSelectedActionId(null)}
              className="flex h-7 w-7 items-center justify-center rounded-lg border transition-all duration-200 hover:bg-[rgba(248,113,113,0.1)] hover:border-[rgba(248,113,113,0.3)]"
              style={{
                backgroundColor: "rgba(255,255,255,0.03)",
                borderColor: "rgba(255,255,255,0.06)",
              }}
            >
              <X className="h-3.5 w-3.5 text-[#94a3b8]" />
            </button>
          </div>
          <ExecutionForm
            actionId={selectedActionId}
            onExecute={handleExecute}
            isLoading={executeMutation.isPending}
          />
        </div>
      )}

      {/* ── Execution History Section ── */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-[rgba(96,165,250,0.1)] p-2.5 shadow-[0_0_12px_rgba(96,165,250,0.15)]">
            <History className="h-4 w-4 text-[#60a5fa]" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-[#e2e8f0]">
              Execution History
            </h2>
            <p className="text-xs text-[#64748b]">
              Recent action executions and their results
            </p>
          </div>
          {execData && execData.total > 0 && (
            <Badge
              label={`${execData.total} total`}
              variant="gray"
            />
          )}
        </div>

        <ExecutionHistory executions={execData?.executions ?? []} />

        {execTotalPages > 1 && (
          <Pagination
            page={execPage}
            totalPages={execTotalPages}
            onPageChange={setExecPage}
          />
        )}
      </div>
    </div>
  );
}
