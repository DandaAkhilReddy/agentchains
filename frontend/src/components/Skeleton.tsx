interface Props {
  className?: string;
}

export default function Skeleton({ className = "" }: Props) {
  return (
    <div
      className={`rounded-lg ${className}`}
      style={{
        background:
          "linear-gradient(90deg, #1a2035 0%, #243052 50%, #1a2035 100%)",
        backgroundSize: "200% 100%",
        animation: "skeleton-shimmer 2s infinite",
      }}
    />
  );
}

export function SkeletonCard() {
  return (
    <div
      className="rounded-2xl border border-[#1a2035] space-y-3 p-5"
      style={{ background: "#141928" }}
    >
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
    <div
      className="overflow-hidden rounded-2xl border border-[#1a2035]"
      style={{ background: "#141928" }}
    >
      <div className="p-4" style={{ background: "rgba(26, 32, 53, 0.5)" }}>
        <Skeleton className="h-3 w-full" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex gap-4 border-t border-[#1a2035]/50 p-4"
        >
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
    <div
      className="rounded-2xl border border-[#1a2035] p-5 space-y-2"
      style={{ background: "#141928" }}
    >
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
    <div
      className="rounded-2xl border border-[#1a2035] p-4 space-y-3"
      style={{ background: "#141928" }}
    >
      <Skeleton className="h-3 w-32" />
      <Skeleton className="h-48 w-full rounded-lg" />
    </div>
  );
}
