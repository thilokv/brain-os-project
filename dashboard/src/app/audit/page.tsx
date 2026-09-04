import { ClipboardList, FileWarning, ShieldCheck, UserCheck } from "lucide-react";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { ChartCard, SectionHeading } from "@/components/dashboard/chart-card";
import { AuditLogTable } from "@/components/dashboard/audit-log-table";
import { auditLog, kpis, workflows } from "@/lib/mock-data";

export default function AuditCenterPage() {
  const humanDecisions = auditLog.filter((e) => e.action === "human_in_loop.decision").length;
  const rejections = auditLog.filter((e) => e.action === "human_in_loop.decision" && e.status === "rejected").length;

  return (
    <div className="flex flex-col gap-6">
      <SectionHeading
        title="Audit center"
        description="Complete, timestamped record of every workflow action -- built for compliance review."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Audit events logged" value={auditLog.length.toLocaleString()} icon={ClipboardList} caption="last 120 days" />
        <KpiCard label="Human decisions recorded" value={humanDecisions.toLocaleString()} icon={UserCheck} caption="approve / reject" />
        <KpiCard label="Rejections with rationale" value={rejections.toLocaleString()} icon={FileWarning} caption="100% have a note on file" />
        <KpiCard label="Workflows fully traceable" value={`${kpis.totalProcessed.toLocaleString()}`} icon={ShieldCheck} caption="intake to briefing" />
      </div>

      <ChartCard
        title="Audit log"
        description="Every action Brain OS took, in order. Filter, search, and export for compliance review."
      >
        <AuditLogTable events={auditLog} workflows={workflows} />
      </ChartCard>
    </div>
  );
}
