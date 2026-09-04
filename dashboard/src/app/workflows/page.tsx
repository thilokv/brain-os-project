import { AlertTriangle, CheckCircle2, Gauge, TimerReset, Zap } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { ChartCard, SectionHeading } from "@/components/dashboard/chart-card";
import { PipelineStepper } from "@/components/dashboard/pipeline-stepper";
import { ErrorRateChart } from "@/components/dashboard/charts/error-rate-chart";
import { StatusBreakdownList } from "@/components/dashboard/status-breakdown-list";
import { errorRateTrend, kpis, pipelineStages, processingMetrics, statusBreakdown } from "@/lib/mock-data";
import { formatDuration, formatPercent } from "@/lib/format";

export default function WorkflowMonitoringPage() {
  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Workflow monitoring"
        description="Live view of the invoice approval pipeline: throughput, stage health, and error rates."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiCard label="Throughput" value={`${processingMetrics.throughputPerDay}/day`} icon={Zap} caption="avg invoices processed" />
        <KpiCard label="Avg. processing time" value={formatDuration(kpis.avgProcessingSeconds)} icon={TimerReset} caption="intake to completion" />
        <KpiCard label="Success rate" value={formatPercent(processingMetrics.successRate)} icon={CheckCircle2} caption="last 30 days" />
        <KpiCard
          label="Error rate"
          value={formatPercent(processingMetrics.errorRate7d)}
          icon={AlertTriangle}
          delta={{
            value: `${Math.abs(processingMetrics.errorRate7d - processingMetrics.errorRate30d).toFixed(1)} pts`,
            direction: processingMetrics.errorRate7d <= processingMetrics.errorRate30d ? "down" : "up",
            positive: processingMetrics.errorRate7d <= processingMetrics.errorRate30d,
          }}
          caption="vs. 30-day avg"
        />
        <KpiCard label="In-flight now" value={kpis.awaitingCount.toLocaleString()} icon={Gauge} caption="awaiting approval" />
      </div>

      <ChartCard title="Workflow pipeline" description="Snapshot of invoices currently in each stage of the LangGraph workflow.">
        <PipelineStepper stages={pipelineStages} />
      </ChartCard>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard
          title="Error rate trend"
          description="Share of workflow runs that failed a step, last 30 days."
          className="lg:col-span-2"
        >
          <ErrorRateChart data={errorRateTrend} />
        </ChartCard>

        <ChartCard title="Status breakdown" description="All workflows, current period">
          <StatusBreakdownList counts={statusBreakdown} />
        </ChartCard>
      </div>
    </div>
  );
}
