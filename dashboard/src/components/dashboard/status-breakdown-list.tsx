import { STATUS_COLORS } from "@/lib/chart-colors";
import type { WorkflowStatus } from "@/lib/types";

const ROWS: { status: WorkflowStatus; label: string; color: string }[] = [
  { status: "completed", label: "Completed", color: STATUS_COLORS.good },
  { status: "auto_approved", label: "Auto-approved", color: STATUS_COLORS.good },
  { status: "awaiting_approval", label: "Awaiting approval", color: STATUS_COLORS.warning },
  { status: "rejected", label: "Rejected", color: STATUS_COLORS.critical },
];

export function StatusBreakdownList({ counts }: { counts: Record<WorkflowStatus, number> }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0);

  return (
    <div className="flex flex-col gap-3.5">
      {ROWS.map((row) => {
        const count = counts[row.status];
        const pct = total > 0 ? (count / total) * 100 : 0;
        return (
          <div key={row.status} className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 font-medium text-foreground">
                <span className="size-2 rounded-full" style={{ backgroundColor: row.color }} />
                {row.label}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {count} · {pct.toFixed(0)}%
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: row.color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
