import { AlertOctagon, ScanSearch, ShieldAlert, TrendingUp } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { ChartCard, SectionHeading } from "@/components/dashboard/chart-card";
import { RiskTrendChart } from "@/components/dashboard/charts/risk-trend-chart";
import { AnomalySummaryList } from "@/components/dashboard/anomaly-summary-list";
import { TopFindingsList } from "@/components/dashboard/top-findings-list";
import { anomalyInsights, anomalySummary, riskTrend, topFindings } from "@/lib/mock-data";
import { formatCompactCurrency, formatPercent } from "@/lib/format";

export default function AiInsightsPage() {
  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="AI insights"
        description="Patterns the risk engine and vector memory have surfaced across recent invoice activity."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Anomaly detection rate"
          value={formatPercent(anomalyInsights.detectionRate)}
          icon={ScanSearch}
          caption="of invoices flagged"
        />
        <KpiCard
          label="High-severity findings"
          value={anomalyInsights.highSeverityCount.toLocaleString()}
          icon={AlertOctagon}
          caption="forced manual review"
        />
        <KpiCard
          label="Value at risk"
          value={formatCompactCurrency(anomalyInsights.totalAtRisk)}
          icon={ShieldAlert}
          caption="across flagged invoices"
        />
        <KpiCard
          label="Avg. risk score trend"
          value={`${riskTrend[riskTrend.length - 1].avgRiskScore}/100`}
          icon={TrendingUp}
          delta={{
            value: `${Math.abs(riskTrend[riskTrend.length - 1].avgRiskScore - riskTrend[riskTrend.length - 2].avgRiskScore).toFixed(1)} pts`,
            direction: riskTrend[riskTrend.length - 1].avgRiskScore <= riskTrend[riskTrend.length - 2].avgRiskScore ? "down" : "up",
            positive: riskTrend[riskTrend.length - 1].avgRiskScore <= riskTrend[riskTrend.length - 2].avgRiskScore,
          }}
          caption="vs. prior week"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ChartCard title="Top findings" description="Highest-risk anomalies surfaced this period, most severe first" className="lg:col-span-2">
          <TopFindingsList findings={topFindings} />
        </ChartCard>

        <div className="flex flex-col gap-4">
          <ChartCard title="Risk score trend" description="12-week rolling average">
            <RiskTrendChart data={riskTrend} />
          </ChartCard>
        </div>
      </div>

      <ChartCard title="Anomaly detection summary" description="Findings by category, with week-over-week movement">
        <AnomalySummaryList entries={anomalySummary} />
      </ChartCard>
    </div>
  );
}
