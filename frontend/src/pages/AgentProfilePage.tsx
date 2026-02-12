import { Bot, Package, ShoppingCart, Target, Users, ArrowLeft } from "lucide-react";
import AnimatedCounter from "../components/AnimatedCounter";
import Badge from "../components/Badge";
import ProgressRing from "../components/ProgressRing";
import EarningsChart from "../components/EarningsChart";
import CategoryPieChart from "../components/CategoryPieChart";
import PageHeader from "../components/PageHeader";
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
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <SkeletonCard />
          <SkeletonCard />
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

  const helpPercent = Math.round(profile.helpfulness_score * 100);

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title={profile.agent_name}
        subtitle={profile.primary_specialization || "Agent Profile"}
        icon={Bot}
        actions={
          <button
            onClick={onBack}
            className="btn-ghost flex items-center gap-1.5 px-3 py-2 text-sm"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
        }
      />

      {/* Hero Card */}
      <div className="glass-card gradient-border-card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-glow text-lg font-bold text-primary">
              {profile.agent_name.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-xl font-bold text-text-primary">{profile.agent_name}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-2">
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
          </div>
          <div className="flex flex-col items-center">
            <ProgressRing value={helpPercent} size={72} strokeWidth={5} color="cyan" />
            <p className="mt-1 text-xs text-text-secondary">Helpfulness</p>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatBox
          icon={<Users className="h-4 w-4 text-primary" />}
          label="Unique Buyers Served"
          value={profile.unique_buyers_served}
        />
        <StatBox
          icon={<Package className="h-4 w-4 text-success" />}
          label="Listings Created"
          value={profile.total_listings_created}
        />
        <StatBox
          icon={<ShoppingCart className="h-4 w-4 text-warning" />}
          label="Cache Hits (Reuse)"
          value={profile.total_cache_hits}
        />
        <StatBox
          icon={<Target className="h-4 w-4 text-secondary" />}
          label="Gaps Filled"
          value={profile.demand_gaps_filled}
        />
      </div>

      {/* Financial Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="glass-card gradient-border-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Total Earned</p>
          <p className="mt-1 text-2xl font-bold text-success" style={{ fontFamily: "var(--font-mono)" }}>
            ${profile.total_earned_usdc.toFixed(4)}
          </p>
        </div>
        <div className="glass-card gradient-border-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Total Spent</p>
          <p className="mt-1 text-2xl font-bold text-danger" style={{ fontFamily: "var(--font-mono)" }}>
            ${profile.total_spent_usdc.toFixed(4)}
          </p>
        </div>
        <div className="glass-card gradient-border-card p-4">
          <p className="text-xs font-semibold uppercase tracking-widest text-text-secondary">Net Revenue</p>
          <p className={`mt-1 text-2xl font-bold ${
            profile.total_earned_usdc - profile.total_spent_usdc >= 0 ? "text-success" : "text-danger"
          }`} style={{ fontFamily: "var(--font-mono)" }}>
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
      <p className="text-2xl font-bold text-text-primary" style={{ fontFamily: "var(--font-mono)" }}>
        <AnimatedCounter value={value} />
      </p>
    </div>
  );
}
