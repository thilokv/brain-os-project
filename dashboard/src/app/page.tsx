import { Clock3, DollarSign, FileCheck2, Hourglass, TrendingUp, Wallet } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { ChartCard, SectionHeading } from "@/components/dashboard/chart-card";
import { RoiBreakdown } from "@/components/dashboard/roi-breakdown";
import { OpenWorkflows } from "@/components/dashboard/open-workflows";
import { SavingsTrendChart } from "@/components/dashboard/charts/savings-trend-chart";
import { kpis, openWorkflowsByDepartment, savingsTrend } from "@/lib/mock-data";
import { formatCompactCurrency, formatCurrency, formatDuration, formatPercent } from "@/lib/format";

export default function ExecutiveDashboardPage() {
  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Executive summary"
        description="Invoice processing performance and cost impact across the last 120 days."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard
          label="Invoices processed"
          value={kpis.totalProcessed.toLocaleString()}
          icon={FileCheck2}
          delta={{ value: "12.4%", direction: "up", positive: true }}
          caption="vs. prior period"
        />
        <KpiCard
          label="Value processed"
          value={formatCompactCurrency(kpis.totalValue)}
          icon={DollarSign}
          delta={{ value: "8.1%", direction: "up", positive: true }}
          caption="vs. prior period"
        />
        <KpiCard
          label="Auto-approval rate"
          value={formatPercent(kpis.autoApprovalRate)}
          icon={TrendingUp}
          delta={{ value: "3.2 pts", direction: "up", positive: true }}
          caption="vs. prior period"
        />
        <KpiCard
          label="Total savings"
          value={formatCompactCurrency(kpis.totalSavings)}
          icon={Wallet}
          delta={{ value: "15.7%", direction: "up", positive: true }}
          caption="vs. prior period"
        />
        <KpiCard
          label="Avg. processing time"
          value={formatDuration(kpis.avgProcessingSeconds)}
          icon={Clock3}
          delta={{ value: "9.8%", direction: "down", positive: true }}
          caption="vs. prior period"
        />
        <KpiCard
          label="Awaiting approval"
          value={kpis.awaitingCount.toLocaleString()}
          icon={Hourglass}
          caption="require human review"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard
          title="Savings trend"
          description="Verified cost savings from automated invoice processing, by month."
          className="lg:col-span-2"
        >
          <SavingsTrendChart data={savingsTrend} />
        </ChartCard>

        <div className="flex flex-col gap-4">
          <ChartCard title="Return on investment" description="This month, vs. platform cost">
            <RoiBreakdown
              roi={kpis.roi}
              totalSavings={kpis.totalSavings}
              laborSavings={kpis.laborSavings}
              duplicateSavings={kpis.duplicateSavings}
              platformCost={kpis.platformCost}
            />
          </ChartCard>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard
          title="Open workflow counts"
          description="Invoices currently paused for human approval, by requesting department."
          className="lg:col-span-2"
        >
          <OpenWorkflows totalOpen={kpis.awaitingCount} byDepartment={openWorkflowsByDepartment} />
        </ChartCard>

        <ChartCard title="Program health" description="At a glance">
          <div className="flex flex-col divide-y divide-border">
            <div className="flex items-center justify-between py-3 first:pt-0">
              <span className="text-sm text-muted-foreground">Duplicate invoices caught</span>
              <span className="text-sm font-medium tabular-nums">{kpis.duplicatesCaught}</span>
            </div>
            <div className="flex items-center justify-between py-3">
              <span className="text-sm text-muted-foreground">Analyst hours reclaimed</span>
              <span className="text-sm font-medium tabular-nums">{kpis.hoursSaved.toLocaleString()}h</span>
            </div>
            <div className="flex items-center justify-between py-3">
              <span className="text-sm text-muted-foreground">Rejected this period</span>
              <span className="text-sm font-medium tabular-nums">{kpis.rejectedCount}</span>
            </div>
            <div className="flex items-center justify-between py-3 last:pb-0">
              <span className="text-sm text-muted-foreground">Net savings per invoice</span>
              <span className="text-sm font-medium tabular-nums">
                {formatCurrency(kpis.totalSavings / kpis.totalProcessed)}
              </span>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}
