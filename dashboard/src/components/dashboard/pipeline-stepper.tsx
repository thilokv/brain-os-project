import { ChevronRight } from "lucide-react";
import { STATUS_COLORS } from "@/lib/chart-colors";
import { formatDuration } from "@/lib/format";
import type { PipelineStage } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<PipelineStage["status"], string> = {
  good: "Healthy",
  warning: "Elevated",
  serious: "Degraded",
  critical: "Blocked",
};

export function PipelineStepper({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="flex flex-col gap-2 lg:flex-row lg:items-stretch lg:gap-0">
      {stages.map((stage, i) => (
        <div key={stage.key} className="flex flex-1 items-stretch lg:contents">
          <div className="flex flex-1 flex-col gap-2.5 rounded-lg border border-border bg-card px-4 py-3.5 lg:rounded-none lg:border-0 lg:border-r lg:last:border-r-0">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Stage {i + 1}</span>
              <span
                className="inline-flex items-center gap-1.5 text-[11px] font-medium"
                style={{ color: STATUS_COLORS[stage.status] }}
              >
                <span className="size-1.5 rounded-full" style={{ backgroundColor: STATUS_COLORS[stage.status] }} />
                {STATUS_LABEL[stage.status]}
              </span>
            </div>
            <p className="text-sm font-semibold text-foreground">{stage.label}</p>
            <div className="flex items-baseline gap-1.5">
              <span className="text-xl font-semibold tabular-nums text-foreground">{stage.count}</span>
              <span className="text-xs text-muted-foreground">in progress</span>
            </div>
            <p className="text-xs tabular-nums text-muted-foreground">avg {formatDuration(stage.avgSeconds)}</p>
          </div>
          {i < stages.length - 1 && (
            <div className={cn("hidden shrink-0 items-center justify-center px-1 lg:flex")}>
              <ChevronRight className="size-4 text-muted-foreground/40" />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
