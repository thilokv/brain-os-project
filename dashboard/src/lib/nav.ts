import type { LucideIcon } from "lucide-react";
import { Activity, LayoutDashboard, ScrollText, Sparkles } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Executive Dashboard",
    description: "KPIs, ROI, and savings",
    icon: LayoutDashboard,
  },
  {
    href: "/workflows",
    label: "Workflow Monitoring",
    description: "Pipeline and processing health",
    icon: Activity,
  },
  {
    href: "/audit",
    label: "Audit Center",
    description: "Audit log and evidence",
    icon: ScrollText,
  },
  {
    href: "/insights",
    label: "AI Insights",
    description: "Findings, risk, and anomalies",
    icon: Sparkles,
  },
];
