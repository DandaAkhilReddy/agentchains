export default function DarkSkeletonCard() {
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
