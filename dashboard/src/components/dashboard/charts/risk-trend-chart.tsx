"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltipCard } from "@/components/dashboard/chart-primitives";
import { CHART_AXIS_COLOR, CHART_COLORS, CHART_GRID_COLOR } from "@/lib/chart-colors";
import type { RiskTrendPoint } from "@/lib/types";

export function RiskTrendChart({ data }: { data: RiskTrendPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={CHART_GRID_COLOR} strokeDasharray="3 3" />
        <XAxis dataKey="week" tickLine={false} axisLine={false} tick={{ fill: CHART_AXIS_COLOR, fontSize: 12 }} dy={8} interval={1} />
        <YAxis
          domain={[0, 100]}
          tickLine={false}
          axisLine={false}
          tick={{ fill: CHART_AXIS_COLOR, fontSize: 12 }}
          width={32}
        />
        <Tooltip
          cursor={{ stroke: CHART_GRID_COLOR, strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const point = payload[0].payload as RiskTrendPoint;
            return (
              <ChartTooltipCard
                title={`Week of ${label}`}
                rows={[{ label: "Avg. risk score", value: `${point.avgRiskScore}/100`, color: CHART_COLORS.violet }]}
              />
            );
          }}
        />
        <Line
          type="monotone"
          dataKey="avgRiskScore"
          stroke={CHART_COLORS.violet}
          strokeWidth={2}
          dot={{ r: 3, strokeWidth: 0, fill: CHART_COLORS.violet }}
          activeDot={{ r: 5, strokeWidth: 0 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
