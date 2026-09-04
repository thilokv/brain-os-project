// Fixed categorical order -- validated via the dataviz skill's palette
// validator (adjacent CVD >= 8, normal-vision >= 15 in both light and dark).
// Never cycle or reassign these by rank; a series keeps its color everywhere.
export const CHART_COLORS = {
  blue: "var(--chart-1)",
  orange: "var(--chart-2)",
  aqua: "var(--chart-3)",
  yellow: "var(--chart-4)",
  violet: "var(--chart-5)",
} as const;

export const CHART_COLOR_LIST = [
  CHART_COLORS.blue,
  CHART_COLORS.orange,
  CHART_COLORS.aqua,
  CHART_COLORS.yellow,
  CHART_COLORS.violet,
];

export const STATUS_COLORS = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  serious: "var(--status-serious)",
  critical: "var(--status-critical)",
} as const;

export const CHART_GRID_COLOR = "var(--border)";
export const CHART_AXIS_COLOR = "var(--muted-foreground)";
