import { useState, useMemo } from "react";
import {
  GitBranch,
  Activity,
  Zap,
  Clock,
  CheckCircle2,
  AlertTriangle,
  BarChart3,
} from "lucide-react";
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

function MetricCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: typeof Activity;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-4">
      <div className="flex items-center gap-3">
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
          style={{ backgroundColor: `${color}15` }}
        >
          <Icon className="h-4 w-4" style={{ color }} />
        </div>
        <div>
          <p className="text-lg font-bold text-[#e2e8f0]">{value}</p>
          <p className="text-[11px] text-[#64748b] font-medium">{label}</p>
        </div>
      </div>
    </div>
  );
}

export default function PipelinePage() {
  const [subTab, setSubTab] = useState("executions");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const { executions, liveEvents, totalSteps } = usePipelineFeed();

  const selectedExecution = selectedAgentId
    ? executions.find((e) => e.agentId === selectedAgentId)
    : executions[0];

  // Compute metrics
  const metrics = useMemo(() => {
    const activeCount = executions.filter(
      (e) => e.status === "active",
    ).length;
    const errorCount = executions.filter(
      (e) => e.status === "error",
    ).length;
    const allSteps = executions.flatMap((e) => e.steps);
    const completedSteps = allSteps.filter((s) => s.status === "completed");
    const avgLatency =
      completedSteps.length > 0
        ? Math.round(
            completedSteps.reduce(
              (sum, s) => sum + (s.latencyMs ?? 0),
              0,
            ) / completedSteps.length,
          )
        : 0;
    const successRate =
      allSteps.length > 0
        ? Math.round((completedSteps.length / allSteps.length) * 100)
        : 100;
    return { activeCount, errorCount, avgLatency, successRate };
  }, [executions]);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Agent Pipeline"
          subtitle={`${executions.length} agents tracked \u00b7 ${totalSteps} steps recorded`}
          icon={GitBranch}
        />
        <SubTabNav tabs={SUB_TABS} active={subTab} onChange={setSubTab} />
      </div>

      {/* Metrics bar */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Total Steps"
          value={totalSteps}
          icon={BarChart3}
          color="#60a5fa"
        />
        <MetricCard
          label="Active Executions"
          value={metrics.activeCount}
          icon={Activity}
          color="#34d399"
        />
        <MetricCard
          label="Avg Latency"
          value={`${metrics.avgLatency}ms`}
          icon={Zap}
          color="#fbbf24"
        />
        <MetricCard
          label="Success Rate"
          value={`${metrics.successRate}%`}
          icon={CheckCircle2}
          color="#a78bfa"
        />
      </div>

      {subTab === "executions" ? (
        executions.length === 0 ? (
          <div className="rounded-2xl border border-[rgba(255,255,255,0.06)] bg-[#141928] p-12 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-[rgba(96,165,250,0.08)] mb-4">
              <Clock className="h-8 w-8 text-[#60a5fa]" />
            </div>
            <p className="text-base font-semibold text-[#e2e8f0] mb-1">
              Waiting for agent activity
            </p>
            <p className="text-sm text-[#64748b] max-w-md mx-auto">
              Agent executions will appear here in real-time as marketplace
              events flow through the WebSocket pipeline.
            </p>
            <div className="mt-5 flex items-center justify-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#60a5fa] animate-pulse" />
              <span className="h-2 w-2 rounded-full bg-[#60a5fa] animate-pulse [animation-delay:200ms]" />
              <span className="h-2 w-2 rounded-full bg-[#60a5fa] animate-pulse [animation-delay:400ms]" />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
            <AgentPipelineList
              executions={executions}
              selectedId={selectedAgentId}
              onSelect={setSelectedAgentId}
            />
            <ExecutionTimeline execution={selectedExecution ?? null} />
          </div>
        )
      ) : (
        <LiveEventFeed events={liveEvents} />
      )}

      {/* Error summary if any */}
      {metrics.errorCount > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-[rgba(248,113,113,0.2)] bg-[rgba(248,113,113,0.05)] px-4 py-3">
          <AlertTriangle className="h-4 w-4 text-[#f87171] shrink-0" />
          <p className="text-sm text-[#f87171]">
            {metrics.errorCount} agent
            {metrics.errorCount === 1 ? "" : "s"} reporting errors
          </p>
        </div>
      )}
    </div>
  );
}
