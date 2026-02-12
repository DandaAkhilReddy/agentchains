import { Radio, ArrowRight, Zap, TrendingUp, Package, Award } from "lucide-react";
import type { FeedEvent } from "../../types/api";

const EVENT_ICONS: Record<string, typeof Radio> = {
  listing_created: Package,
  transaction_completed: ArrowRight,
  express_purchase: Zap,
  demand_spike: TrendingUp,
  leaderboard_change: Award,
};

const EVENT_COLORS: Record<string, string> = {
  listing_created: "text-primary bg-primary-glow",
  transaction_completed: "text-success bg-success/10",
  express_purchase: "text-secondary bg-secondary-glow",
  demand_spike: "text-warning bg-warning-glow",
  leaderboard_change: "text-primary bg-primary-glow",
};

interface Props {
  events: FeedEvent[];
}

export default function LiveEventFeed({ events }: Props) {
  if (events.length === 0) {
    return (
      <div className="glass-card p-8 text-center">
        <Radio className="mx-auto h-10 w-10 text-text-muted mb-3" />
        <p className="text-sm font-medium text-text-secondary">Listening for live events...</p>
        <p className="text-xs text-text-muted mt-1">
          Events from the marketplace WebSocket feed will appear here in real-time.
        </p>
        <div className="mt-4 flex items-center justify-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
          <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse [animation-delay:200ms]" />
          <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse [animation-delay:400ms]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
        <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">
          Live Feed ({events.length} events)
        </p>
      </div>
      <div className="space-y-1.5">
        {events.map((event, i) => {
          const Icon = EVENT_ICONS[event.type] ?? Radio;
          const color = EVENT_COLORS[event.type] ?? "text-text-muted bg-surface-overlay";
          return (
            <div
              key={`${event.type}-${i}`}
              className="glass-card-subtle flex items-center gap-3 p-3 rounded-xl animate-slide-in"
              style={{ animationDelay: `${i * 30}ms` }}
            >
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${color}`}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary capitalize">
                  {event.type.replace(/_/g, " ")}
                </p>
                <p className="text-xs text-text-muted truncate">
                  {JSON.stringify(event).slice(0, 120)}...
                </p>
              </div>
              <span className="text-xs font-mono text-text-muted shrink-0">
                {new Date().toLocaleTimeString()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
