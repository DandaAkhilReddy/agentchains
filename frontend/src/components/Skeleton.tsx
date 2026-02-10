interface Props {
  className?: string;
}

export default function Skeleton({ className = "" }: Props) {
  return (
    <div className={`animate-pulse rounded-lg bg-zinc-800/50 ${className}`} />
  );
}

export function SkeletonCard() {
  return (
    <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
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
    <div className="overflow-hidden rounded-xl border border-zinc-800">
      <div className="bg-zinc-900/50 p-4">
        <Skeleton className="h-3 w-full" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 border-t border-zinc-800/50 p-4">
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-3 w-1/4" />
          <Skeleton className="h-3 w-1/6" />
          <Skeleton className="h-3 w-1/6" />
        </div>
      ))}
    </div>
  );
}
