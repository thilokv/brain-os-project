"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/lib/nav";

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2.5 px-5 py-6">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
          <Brain className="size-5" strokeWidth={2.25} />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight text-white">Brain OS</span>
          <span className="text-[11px] text-sidebar-foreground/60">Enterprise Workflow Platform</span>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        <p className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-wider text-sidebar-foreground/40">
          Workspace
        </p>
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-white"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-white",
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-sidebar-primary" />
              )}
              <Icon className={cn("size-4.5 shrink-0", isActive ? "text-sidebar-primary" : "text-sidebar-foreground/50 group-hover:text-white")} />
              <span className="flex-1 truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border px-4 py-4">
        <div className="flex items-center gap-2 rounded-md bg-sidebar-accent/50 px-3 py-2.5">
          <span className="relative flex size-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-good opacity-60" />
            <span className="relative inline-flex size-2 rounded-full bg-status-good" />
          </span>
          <div className="flex flex-1 flex-col leading-tight">
            <span className="text-xs font-medium text-white">All systems operational</span>
            <span className="text-[11px] text-sidebar-foreground/50">Brain OS API v0.1.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
