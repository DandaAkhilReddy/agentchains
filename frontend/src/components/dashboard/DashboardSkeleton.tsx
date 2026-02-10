import { Skeleton } from "../shared/Skeleton";

export function DashboardSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="bg-[var(--color-bg-card)] rounded-xl p-5 border border-[var(--color-border-subtle)]"
          >
            <div className="flex items-center gap-3 mb-3">
              <Skeleton circle className="w-10 h-10" />
              <Skeleton className="w-24 h-4" />
            </div>
            <Skeleton className="w-32 h-7 mb-2" />
            <Skeleton className="w-20 h-3" />
          </div>
        ))}
      </div>

      {/* Loan cards */}
      <div className="space-y-3">
        <Skeleton className="w-40 h-5" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="bg-[var(--color-bg-card)] rounded-xl p-5 border border-[var(--color-border-subtle)]"
            >
              <Skeleton lines={3} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
