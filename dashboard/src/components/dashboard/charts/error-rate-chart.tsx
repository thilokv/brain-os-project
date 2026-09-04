"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltipCard } from "@/components/dashboard/chart-primitives";
import { CHART_AXIS_COLOR, CHART_GRID_COLOR, STATUS_COLORS } from "@/lib/chart-colors";
import type { ErrorRatePoint } from "@/lib/types";

export function ErrorRateChart({ data }: { data: ErrorRatePoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={CHART_GRID_COLOR} strokeDasharray="3 3" />
        <XAxis
          dataKey="date"
          tickLine={false}
          axisLine={false}
          interval={4}
          tick={{ fill: CHART_AXIS_COLOR, fontSize: 12 }}
          dy={8}
        />
        <YAxis
          tickFormatter={(v: number) => `${v}%`}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_AXIS_COLOR, fontSize: 12 }}
          width={40}
        />
        <Tooltip
          cursor={{ stroke: CHART_GRID_COLOR, strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const point = payload[0].payload as ErrorRatePoint;
            return (
              <ChartTooltipCard
                title={label as string}
                rows={[
                  { label: "Error rate", value: `${point.errorRate}%`, color: STATUS_COLORS.critical },
                  { label: "Errors", value: `${point.errors} / ${point.totalRuns} runs` },
                ]}
              />
            );
          }}
        />
        <Line
          type="monotone"
          dataKey="errorRate"
          stroke={STATUS_COLORS.critical}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
