import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { SeverityBadge } from "@/components/dashboard/status-badge";
import { formatPercent } from "@/lib/format";
import type { AnomalySummaryEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AnomalySummaryList({ entries }: { entries: AnomalySummaryEntry[] }) {
  const maxCount = Math.max(1, ...entries.map((e) => e.count));

  return (
    <div className="flex flex-col gap-4">
      {entries.map((entry) => {
        const trendIsIncrease = entry.trend > 0;
        // For anomaly counts, a decrease is the good outcome -- an increasing
        // trend is flagged with the destructive color, not the default "up = good" mapping.
        const trendPositive = !trendIsIncrease;
        return (
          <div key={entry.code} className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{entry.label}</span>
                <SeverityBadge severity={entry.severity} />
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
                    trendPositive ? "text-status-good-text" : "text-destructive",
                  )}
                >
                  {trendIsIncrease ? <ArrowUpRight className="size-3.5" /> : <ArrowDownRight className="size-3.5" />}
                  {formatPercent(Math.abs(entry.trend))}
                </span>
                <span className="w-8 text-right text-sm font-semibold tabular-nums text-foreground">{entry.count}</span>
              </div>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-chart-5 transition-all"
                style={{ width: `${(entry.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
