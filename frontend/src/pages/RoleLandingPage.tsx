import { Bot, Shield, UserRound } from "lucide-react";

import PageHeader from "../components/PageHeader";

interface Props {
  onNavigate: (tab: string) => void;
}

const CARDS = [
  {
    id: "agentDashboard",
    label: "Agent Dashboard",
    subtitle: "Track revenue, usage, trust, and saved spend for buyers.",
    icon: Bot,
    accent: "#60a5fa",
  },
  {
    id: "creator",
    label: "Creator Dashboard",
    subtitle: "Manage your agent fleet, earnings, and payout workflow.",
    icon: UserRound,
    accent: "#34d399",
  },
  {
    id: "adminDashboard",
    label: "Admin Dashboard",
    subtitle: "Platform finance, risk, security events, and payout approvals.",
    icon: Shield,
    accent: "#fbbf24",
  },
];

export default function RoleLandingPage({ onNavigate }: Props) {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Role Landing"
        subtitle="Choose your login and dashboard context"
        icon={Shield}
      />

      <div className="grid gap-4 md:grid-cols-3">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <button
              key={card.id}
              onClick={() => onNavigate(card.id)}
              className="rounded-2xl border border-[rgba(255,255,255,0.08)] bg-[#141928] p-6 text-left transition-all duration-300 hover:-translate-y-1 hover:border-[rgba(96,165,250,0.4)]"
            >
              <div
                className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl"
                style={{ backgroundColor: `${card.accent}1f` }}
              >
                <Icon className="h-5 w-5" style={{ color: card.accent }} />
              </div>
              <h3 className="text-lg font-semibold text-[#e2e8f0]">{card.label}</h3>
              <p className="mt-2 text-sm text-[#94a3b8]">{card.subtitle}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
