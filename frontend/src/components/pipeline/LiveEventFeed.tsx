import { Radio, ArrowRight, Zap, TrendingUp, Package, Award } from "lucide-react";
import type { FeedEvent } from "../../types/api";

const EVENT_ICONS: Record<string, typeof Radio> = {
  listing_created: Package,
  transaction_completed: ArrowRight,
  express_purchase: Zap,
  demand_spike: TrendingUp,
  leaderboard_change: Award,
};

const EVENT_COLORS: Record<string, { text: string; bg: string }> = {
  listing_created: { text: "#60a5fa", bg: "rgba(96,165,250,0.1)" },
  transaction_completed: { text: "#34d399", bg: "rgba(52,211,153,0.1)" },
  express_purchase: { text: "#a78bfa", bg: "rgba(167,139,250,0.1)" },
  demand_spike: { text: "#fbbf24", bg: "rgba(251,191,36,0.1)" },
  leaderboard_change: { text: "#60a5fa", bg: "rgba(96,165,250,0.1)" },
};

const EVENT_BADGE_COLORS: Record<string, string> = {
  listing_created: "bg-[rgba(96,165,250,0.15)] text-[#60a5fa] border-[rgba(96,165,250,0.25)]",
  transaction_completed: "bg-[rgba(52,211,153,0.15)] text-[#34d399] border-[rgba(52,211,153,0.25)]",
  express_purchase: "bg-[rgba(167,139,250,0.15)] text-[#a78bfa] border-[rgba(167,139,250,0.25)]",
  demand_spike: "bg-[rgba(251,191,36,0.15)] text-[#fbbf24] border-[rgba(251,191,36,0.25)]",
  leaderboard_change: "bg-[rgba(96,165,250,0.15)] text-[#60a5fa] border-[rgba(96,165,250,0.25)]",
};

interface Props {
  events: FeedEvent[];
}

export default function LiveEventFeed({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-12 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)] mb-4">
          <Radio className="h-8 w-8 text-[#60a5fa]" />
        </div>
        <p className="text-base font-semibold text-[#e2e8f0] mb-1">
          Listening for live events...
        </p>
        <p className="text-sm text-[#64748b] max-w-md mx-auto">
          Events from the marketplace WebSocket feed will appear here in real-time.
        </p>
        <div className="mt-5 flex items-center justify-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-[#60a5fa] animate-pulse" />
          <span className="h-2 w-2 rounded-full bg-[#60a5fa] animate-pulse [animation-delay:200ms]" />
          <span className="h-2 w-2 rounded-full bg-[#60a5fa] animate-pulse [animation-delay:400ms]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 px-1">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#34d399] opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[#34d399]" />
        </span>
        <p className="text-[10px] font-bold uppercase tracking-widest text-[#64748b]">
          Live Feed ({events.length} events)
        </p>
      </div>
      <div className="space-y-1.5">
        {events.map((event, i) => {
          const Icon = EVENT_ICONS[event.type] ?? Radio;
          const colors = EVENT_COLORS[event.type] ?? { text: "#64748b", bg: "rgba(100,116,139,0.1)" };
          const badgeClass = EVENT_BADGE_COLORS[event.type] ?? "bg-[rgba(100,116,139,0.15)] text-[#64748b] border-[rgba(100,116,139,0.25)]";
          return (
            <div
              key={`${event.type}-${i}`}
              className="flex items-center gap-3 p-3 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] hover:bg-[#1a2035] transition-colors duration-200 animate-slide-in"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <div
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                style={{ backgroundColor: colors.bg }}
              >
                <Icon className="h-4 w-4" style={{ color: colors.text }} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold border ${badgeClass}`}>
                    {event.type.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="text-xs text-[#64748b] truncate font-mono">
                  {JSON.stringify(event).slice(0, 120)}...
                </p>
              </div>
              <span className="text-[10px] font-mono text-[#64748b] shrink-0">
                {new Date().toLocaleTimeString()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
