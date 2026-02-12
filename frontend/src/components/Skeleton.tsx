interface Props {
  className?: string;
}

export default function Skeleton({ className = "" }: Props) {
  return (
    <div className={`rounded-lg bg-surface-overlay/30 animate-shimmer ${className}`} />
  );
}

export function SkeletonCard() {
  return (
    <div className="glass-card border border-border-subtle space-y-3 p-5">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-3 w-1/3" />
      <Skeleton className="h-8 w-full" />
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-5 w-16" />
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="glass-card overflow-hidden border border-border-subtle">
      <div className="bg-surface-overlay/30 p-4">
        <Skeleton className="h-3 w-full" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 border-t border-border-subtle/30 p-4">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-3 w-1/6" />
          <Skeleton className="h-3 w-1/6" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonStatCard() {
  return (
    <div className="glass-card border border-border-subtle p-5 space-y-2">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-xl" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-6 w-24" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonChart() {
  return (
    <div className="glass-card border border-border-subtle p-4 space-y-3">
      <Skeleton className="h-3 w-32" />
      <Skeleton className="h-48 w-full rounded-lg" />
    </div>
  );
}
