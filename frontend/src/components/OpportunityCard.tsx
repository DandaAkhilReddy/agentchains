import { DollarSign, TrendingUp, Users } from "lucide-react";
import UrgencyBadge from "./UrgencyBadge";

interface Props {
  queryPattern: string;
  category: string | null;
  estimatedRevenue: number;
  searchVelocity: number;
  competingListings: number;
  urgencyScore: number;
}

export default function OpportunityCard({
  queryPattern,
  category,
  estimatedRevenue,
  searchVelocity,
  competingListings,
  urgencyScore,
}: Props) {
  return (
    <div className="glass-card gradient-border-card glow-hover group p-4 transition-all animate-scale-in">
      <div className="mb-3 flex items-start justify-between">
        <div className="flex-1">
          <p className="font-medium text-text-primary">{queryPattern}</p>
          {category && (
            <span className="mt-1 inline-block rounded-full bg-blue-500/20 px-2 py-0.5 text-xs text-blue-400">
              {category}
            </span>
          )}
        </div>
        <UrgencyBadge score={urgencyScore} />
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div className="flex items-center gap-1.5 text-text-secondary">
          <DollarSign className="h-3.5 w-3.5 text-primary" />
          <span className="font-mono text-primary">${estimatedRevenue.toFixed(4)}</span>
        </div>
        <div className="flex items-center gap-1.5 text-text-secondary">
          <TrendingUp className="h-3.5 w-3.5 text-orange-400" />
          <span>{searchVelocity.toFixed(1)}/hr</span>
        </div>
        <div className="flex items-center gap-1.5 text-text-secondary">
          <Users className="h-3.5 w-3.5 text-primary" />
          <span>{competingListings} competing</span>
        </div>
      </div>
    </div>
  );
}
