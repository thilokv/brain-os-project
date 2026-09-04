"use client";

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltipCard } from "@/components/dashboard/chart-primitives";
import { CHART_AXIS_COLOR, CHART_COLORS, CHART_GRID_COLOR } from "@/lib/chart-colors";
import { formatCompactCurrency, formatCurrency } from "@/lib/format";
import type { SavingsTrendPoint } from "@/lib/types";

export function SavingsTrendChart({ data }: { data: SavingsTrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="savingsFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS.blue} stopOpacity={0.28} />
            <stop offset="100%" stopColor={CHART_COLORS.blue} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={CHART_GRID_COLOR} strokeDasharray="3 3" />
        <XAxis
          dataKey="month"
          tickFormatter={(v: string) => v.split(" ")[0]}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_AXIS_COLOR, fontSize: 12 }}
          dy={8}
        />
        <YAxis
          tickFormatter={(v: number) => formatCompactCurrency(v)}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_AXIS_COLOR, fontSize: 12 }}
          width={56}
        />
        <Tooltip
          cursor={{ stroke: CHART_GRID_COLOR, strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const point = payload[0].payload as SavingsTrendPoint;
            return (
              <ChartTooltipCard
                title={label as string}
                rows={[
                  { label: "Savings", value: formatCurrency(point.savedValue), color: CHART_COLORS.blue },
                  { label: "Invoices processed", value: point.invoiceCount.toLocaleString() },
                ]}
              />
            );
          }}
        />
        <Area
          type="monotone"
          dataKey="savedValue"
          stroke={CHART_COLORS.blue}
          strokeWidth={2}
          fill="url(#savingsFill)"
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
