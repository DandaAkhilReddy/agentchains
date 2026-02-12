import { useState } from "react";
import { Cpu } from "lucide-react";
import PageHeader from "../components/PageHeader";
import SubTabNav from "../components/SubTabNav";
import ArchitectureOverview from "../components/technology/ArchitectureOverview";
import SmartRouterViz from "../components/technology/SmartRouterViz";
import AutoMatchViz from "../components/technology/AutoMatchViz";
import CDNTiersViz from "../components/technology/CDNTiersViz";
import ExpressDeliveryViz from "../components/technology/ExpressDeliveryViz";
import ZKPVerificationViz from "../components/technology/ZKPVerificationViz";
import TokenEconomyViz from "../components/technology/TokenEconomyViz";

const TABS = [
  { id: "overview", label: "Architecture" },
  { id: "router", label: "Smart Router" },
  { id: "match", label: "Auto-Match" },
  { id: "cdn", label: "CDN Tiers" },
  { id: "express", label: "Express" },
  { id: "zkp", label: "ZKP" },
  { id: "tokens", label: "Tokens" },
];

export default function TechnologyPage() {
  const [tab, setTab] = useState("overview");

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="System Design"
          subtitle="Architecture, algorithms, and competitive advantages"
          icon={Cpu}
        />
        <SubTabNav tabs={TABS} active={tab} onChange={setTab} />
      </div>

      {tab === "overview" && <ArchitectureOverview onNavigate={setTab} />}
      {tab === "router" && <SmartRouterViz />}
      {tab === "match" && <AutoMatchViz />}
      {tab === "cdn" && <CDNTiersViz />}
      {tab === "express" && <ExpressDeliveryViz />}
      {tab === "zkp" && <ZKPVerificationViz />}
      {tab === "tokens" && <TokenEconomyViz />}
    </div>
  );
}
