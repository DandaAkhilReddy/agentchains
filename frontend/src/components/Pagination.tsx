import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

interface Props {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null;

  const pages: (number | "...")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push("...");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i);
    }
    if (page < totalPages - 2) pages.push("...");
    pages.push(totalPages);
  }

  const btn = "flex h-8 w-8 items-center justify-center rounded-lg text-xs transition-all duration-200";

  return (
    <div className="flex items-center justify-between pt-4">
      <span className="text-xs text-text-muted">
        Page {page} of {totalPages}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={page === 1}
          aria-label="First page"
          className={`${btn} text-text-muted hover:text-text-primary hover:bg-surface-overlay disabled:opacity-30 disabled:cursor-not-allowed`}
        >
          <ChevronsLeft className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 1}
          aria-label="Previous page"
          className={`${btn} text-text-muted hover:text-text-primary hover:bg-surface-overlay disabled:opacity-30 disabled:cursor-not-allowed`}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>

        {pages.map((p, i) =>
          p === "..." ? (
            <span key={`e${i}`} className="px-1 text-xs text-text-muted">...</span>
          ) : (
            <button
              key={p}
              onClick={() => onPageChange(p)}
              className={`${btn} ${
                p === page
                  ? "bg-primary text-white font-bold shadow-[0_0_12px_rgba(59,130,246,0.3)]"
                  : "text-text-secondary hover:text-text-primary hover:bg-surface-overlay"
              }`}
            >
              {p}
            </button>
          ),
        )}

        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page === totalPages}
          aria-label="Next page"
          className={`${btn} text-text-muted hover:text-text-primary hover:bg-surface-overlay disabled:opacity-30 disabled:cursor-not-allowed`}
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={page === totalPages}
          aria-label="Last page"
          className={`${btn} text-text-muted hover:text-text-primary hover:bg-surface-overlay disabled:opacity-30 disabled:cursor-not-allowed`}
        >
          <ChevronsRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
