import { cn } from "@/lib/utils";

interface TooltipRow {
  label: string;
  value: string;
  color?: string;
}

interface ChartTooltipCardProps {
  title?: string;
  rows: TooltipRow[];
}

/** Themed replacement for Recharts' default (unstyled) tooltip. */
export function ChartTooltipCard({ title, rows }: ChartTooltipCardProps) {
  return (
    <div className="min-w-[10rem] rounded-lg border border-border bg-popover px-3 py-2 text-popover-foreground shadow-md">
      {title && <p className="mb-1.5 text-xs font-medium text-muted-foreground">{title}</p>}
      <div className="flex flex-col gap-1">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              {row.color && <span className="size-2 rounded-full" style={{ backgroundColor: row.color }} />}
              {row.label}
            </span>
            <span className="font-medium tabular-nums text-foreground">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

interface LegendEntry {
  label: string;
  color: string;
}

/** Explicit legend row -- every chart with >=2 series ships one (dataviz skill, check 6). */
export function ChartLegend({ entries, className }: { entries: LegendEntry[]; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground", className)}>
      {entries.map((entry) => (
        <span key={entry.label} className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ backgroundColor: entry.color }} />
          {entry.label}
        </span>
      ))}
    </div>
  );
}
