import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string;
  icon: LucideIcon;
  delta?: { value: string; direction: "up" | "down"; positive: boolean };
  caption?: string;
}

export function KpiCard({ label, value, icon: Icon, delta, caption }: KpiCardProps) {
  return (
    <Card className="gap-3 py-5">
      <CardContent className="px-5">
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent text-accent-foreground">
            <Icon className="size-4" strokeWidth={2} />
          </div>
        </div>
        <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight text-foreground sm:text-[1.75rem]">
          {value}
        </p>
        <div className="mt-2 flex items-center gap-1.5">
          {delta && (
            <span
              className={cn(
                "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
                delta.positive ? "text-status-good-text" : "text-destructive",
              )}
            >
              {delta.direction === "up" ? (
                <ArrowUpRight className="size-3.5" />
              ) : (
                <ArrowDownRight className="size-3.5" />
              )}
              {delta.value}
            </span>
          )}
          {caption && <span className="text-xs text-muted-foreground">{caption}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
