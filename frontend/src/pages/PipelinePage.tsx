import { useState } from "react";
import { GitBranch, Radio, Clock } from "lucide-react";
import PageHeader from "../components/PageHeader";
import SubTabNav from "../components/SubTabNav";
import { usePipelineFeed } from "../hooks/usePipelineFeed";
import AgentPipelineList from "../components/pipeline/AgentPipelineList";
import ExecutionTimeline from "../components/pipeline/ExecutionTimeline";
import LiveEventFeed from "../components/pipeline/LiveEventFeed";

const SUB_TABS = [
  { id: "executions", label: "Executions" },
  { id: "live", label: "Live Feed" },
];

export default function PipelinePage() {
  const [subTab, setSubTab] = useState("executions");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const { executions, liveEvents, totalSteps } = usePipelineFeed();

  const selectedExecution = selectedAgentId
    ? executions.find((e) => e.agentId === selectedAgentId)
    : executions[0];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Agent Pipeline"
          subtitle={`${executions.length} agents tracked · ${totalSteps} steps recorded`}
          icon={GitBranch}
        />
        <SubTabNav tabs={SUB_TABS} active={subTab} onChange={setSubTab} />
      </div>

      {subTab === "executions" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
          <AgentPipelineList
            executions={executions}
            selectedId={selectedAgentId}
            onSelect={setSelectedAgentId}
          />
          <ExecutionTimeline execution={selectedExecution ?? null} />
        </div>
      ) : (
        <LiveEventFeed events={liveEvents} />
      )}
    </div>
  );
}
