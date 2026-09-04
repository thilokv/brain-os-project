import { formatCompactCurrency } from "@/lib/format";

interface OpenWorkflowsProps {
  totalOpen: number;
  byDepartment: { department: string; count: number; value: number }[];
}

export function OpenWorkflows({ totalOpen, byDepartment }: OpenWorkflowsProps) {
  const maxCount = Math.max(1, ...byDepartment.map((d) => d.count));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between">
        <p className="text-sm text-muted-foreground">Invoices awaiting approval</p>
        <p className="text-2xl font-semibold tabular-nums text-foreground">{totalOpen}</p>
      </div>

      <div className="flex flex-col gap-3">
        {byDepartment.slice(0, 6).map((row) => (
          <div key={row.department} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-foreground">{row.department}</span>
              <span className="tabular-nums text-muted-foreground">
                {row.count} · {formatCompactCurrency(row.value)}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${(row.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        ))}
        {byDepartment.length === 0 && (
          <p className="text-sm text-muted-foreground">No workflows currently awaiting approval.</p>
        )}
      </div>
    </div>
  );
}
