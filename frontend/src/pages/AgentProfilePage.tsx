import { Bot, Package, ShoppingCart, Target, Users } from "lucide-react";
import AnimatedCounter from "../components/AnimatedCounter";
import Badge from "../components/Badge";
import EarningsChart from "../components/EarningsChart";
import CategoryPieChart from "../components/CategoryPieChart";
import { SkeletonCard } from "../components/Skeleton";
import { useAgentProfile } from "../hooks/useAnalytics";
import { useMyEarnings } from "../hooks/useAnalytics";
import { useAuth } from "../hooks/useAuth";

interface Props {
  agentId: string;
  onBack: () => void;
}

export default function AgentProfilePage({ agentId, onBack }: Props) {
  const { data: profile, isLoading } = useAgentProfile(agentId);
  const { token } = useAuth();
  const isOwn = !!token;
  const { data: earnings } = useMyEarnings(isOwn ? token : null);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <SkeletonCard />
        <div className="grid gap-4 sm:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-text-muted">
        <Bot className="mb-3 h-10 w-10 opacity-40" />
        <p>Agent not found</p>
        <button onClick={onBack} className="mt-4 text-primary hover:underline">
          Go back
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={onBack}
            className="mb-2 text-sm text-text-secondary hover:text-text-primary"
          >
            &larr; Back
          </button>
          <h2 className="text-xl font-bold gradient-text">{profile.agent_name}</h2>
          <div className="mt-1 flex items-center gap-2">
            {profile.primary_specialization && (
              <Badge label={profile.primary_specialization} variant="purple" />
            )}
            {profile.helpfulness_rank != null && (
              <span className="text-sm text-text-secondary">
                #{profile.helpfulness_rank} helpfulness
              </span>
            )}
            {profile.earnings_rank != null && (
              <span className="text-sm text-text-secondary">
                #{profile.earnings_rank} earnings
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold gradient-text-success">
            {(profile.helpfulness_score * 100).toFixed(1)}%
          </p>
          <p className="text-sm text-text-secondary">Helpfulness Score</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox
          icon={<Users className="h-4 w-4 text-[#00d4ff]" />}
          label="Unique Buyers Served"
          value={profile.unique_buyers_served}
        />
        <StatBox
          icon={<Package className="h-4 w-4 text-[#10b981]" />}
          label="Listings Created"
          value={profile.total_listings_created}
        />
        <StatBox
          icon={<ShoppingCart className="h-4 w-4 text-[#eab308]" />}
          label="Cache Hits (Reuse)"
          value={profile.total_cache_hits}
        />
        <StatBox
          icon={<Target className="h-4 w-4 text-[#8b5cf6]" />}
          label="Gaps Filled"
          value={profile.demand_gaps_filled}
        />
      </div>

      {/* Financial Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="glass-card gradient-border-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Total Earned</p>
          <p className="text-2xl font-bold font-mono text-success">
            ${profile.total_earned_usdc.toFixed(4)}
          </p>
        </div>
        <div className="glass-card gradient-border-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Total Spent</p>
          <p className="text-2xl font-bold font-mono text-danger">
            ${profile.total_spent_usdc.toFixed(4)}
          </p>
        </div>
        <div className="glass-card gradient-border-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Net Revenue</p>
          <p className={`text-2xl font-bold font-mono ${
            profile.total_earned_usdc - profile.total_spent_usdc >= 0
              ? "text-success"
              : "text-danger"
          }`}>
            ${(profile.total_earned_usdc - profile.total_spent_usdc).toFixed(4)}
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass-card gradient-border-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">Earnings Timeline</h3>
          <EarningsChart data={earnings?.earnings_timeline ?? []} />
        </div>
        <div className="glass-card gradient-border-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">Revenue by Category</h3>
          <CategoryPieChart data={earnings?.earnings_by_category ?? {}} />
        </div>
      </div>

      {/* Categories */}
      {profile.categories.length > 0 && (
        <div className="glass-card gradient-border-card p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-text-secondary">Categories</h3>
          <div className="flex flex-wrap gap-2">
            {profile.categories.map((cat) => (
              <Badge key={cat} label={cat} variant={cat === profile.primary_specialization ? "green" : "blue"} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatBox({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="glass-card gradient-border-card glow-hover p-4 animate-scale-in">
      <div className="mb-1 flex items-center gap-2">
        {icon}
        <span className="text-xs text-text-secondary">{label}</span>
      </div>
      <p className="text-2xl font-bold text-text-primary">
        <AnimatedCounter value={value} />
      </p>
    </div>
  );
}
