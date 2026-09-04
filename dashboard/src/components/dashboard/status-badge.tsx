import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AnomalySeverity, WorkflowStatus } from "@/lib/types";

const STATUS_CONFIG: Record<WorkflowStatus, { label: string; className: string; dot: string }> = {
  auto_approved: { label: "Auto-approved", className: "bg-status-good/10 text-status-good-text border-status-good/30", dot: "bg-status-good" },
  completed: { label: "Completed", className: "bg-status-good/10 text-status-good-text border-status-good/30", dot: "bg-status-good" },
  awaiting_approval: { label: "Awaiting approval", className: "bg-status-warning/15 text-amber-700 dark:text-status-warning border-status-warning/40", dot: "bg-status-warning" },
  approved: { label: "Approved", className: "bg-status-good/10 text-status-good-text border-status-good/30", dot: "bg-status-good" },
  rejected: { label: "Rejected", className: "bg-status-critical/10 text-status-critical border-status-critical/30", dot: "bg-status-critical" },
};

export function WorkflowStatusBadge({ status }: { status: WorkflowStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge variant="outline" className={cn("gap-1.5 font-medium", config.className)}>
      <span className={cn("size-1.5 rounded-full", config.dot)} />
      {config.label}
    </Badge>
  );
}

const SEVERITY_CONFIG: Record<AnomalySeverity, { label: string; className: string }> = {
  low: { label: "Low", className: "bg-muted text-muted-foreground border-border" },
  medium: { label: "Medium", className: "bg-status-warning/15 text-amber-700 dark:text-status-warning border-status-warning/40" },
  high: { label: "High", className: "bg-status-critical/10 text-status-critical border-status-critical/30" },
};

export function SeverityBadge({ severity }: { severity: AnomalySeverity }) {
  const config = SEVERITY_CONFIG[severity];
  return (
    <Badge variant="outline" className={cn("font-medium", config.className)}>
      {config.label}
    </Badge>
  );
}
