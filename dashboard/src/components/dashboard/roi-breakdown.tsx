import { CHART_COLORS } from "@/lib/chart-colors";
import { formatCurrency, formatPercent } from "@/lib/format";

interface RoiBreakdownProps {
  roi: number;
  totalSavings: number;
  laborSavings: number;
  duplicateSavings: number;
  platformCost: number;
}

export function RoiBreakdown({ roi, totalSavings, laborSavings, duplicateSavings, platformCost }: RoiBreakdownProps) {
  const laborPct = (laborSavings / totalSavings) * 100;
  const duplicatePct = 100 - laborPct;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="text-sm font-medium text-muted-foreground">Return on investment</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums tracking-tight text-status-good-text">
          {formatPercent(roi, { signed: true })}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {formatCurrency(totalSavings)} saved against {formatCurrency(platformCost)} monthly platform cost
        </p>
      </div>

      <div>
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted">
          <div style={{ width: `${laborPct}%`, backgroundColor: CHART_COLORS.blue }} />
          <div style={{ width: `${duplicatePct}%`, backgroundColor: CHART_COLORS.orange }} className="border-l-2 border-card" />
        </div>
        <div className="mt-3 flex flex-col gap-2.5 text-sm">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-muted-foreground">
              <span className="size-2 rounded-full" style={{ backgroundColor: CHART_COLORS.blue }} />
              Analyst labor savings
            </span>
            <span className="font-medium tabular-nums">{formatCurrency(laborSavings)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-muted-foreground">
              <span className="size-2 rounded-full" style={{ backgroundColor: CHART_COLORS.orange }} />
              Duplicate invoices caught
            </span>
            <span className="font-medium tabular-nums">{formatCurrency(duplicateSavings)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
