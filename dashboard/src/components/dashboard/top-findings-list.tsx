import { AlertTriangle } from "lucide-react";
import { SeverityBadge } from "@/components/dashboard/status-badge";
import { formatCurrency, formatDate } from "@/lib/format";
import type { TopFinding } from "@/lib/types";

export function TopFindingsList({ findings }: { findings: TopFinding[] }) {
  return (
    <div className="flex flex-col divide-y divide-border">
      {findings.map((finding) => (
        <div key={finding.id} className="flex items-start gap-3.5 py-3.5 first:pt-0 last:pb-0">
          <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-status-critical/10 text-status-critical">
            <AlertTriangle className="size-4" />
          </div>
          <div className="flex-1">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm font-medium text-foreground">{finding.title}</p>
              <SeverityBadge severity={finding.severity} />
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{finding.summary}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
              <span className="font-mono">{finding.workflowId}</span>
              <span>·</span>
              <span>{formatCurrency(finding.amountAtRisk)} at risk</span>
              <span>·</span>
              <span>{formatDate(finding.detectedAt)}</span>
            </div>
          </div>
        </div>
      ))}
      {findings.length === 0 && <p className="py-6 text-center text-sm text-muted-foreground">No findings in this period.</p>}
    </div>
  );
}
