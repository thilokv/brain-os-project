"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Bell, Menu, Search } from "lucide-react";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const activeItem = NAV_ITEMS.find((item) => item.href === pathname) ?? NAV_ITEMS[0];

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 border-r border-sidebar-border lg:block">
        <SidebarNav />
      </aside>

      {/* Mobile sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        {/* !w-64 (important) is required here, not just w-64: SheetContent's own
            data-[side=left]:w-3/4 rule has an attribute selector, giving it higher
            CSS specificity than a plain w-64 utility regardless of source order --
            confirmed by inspecting the compiled CSS, where w-3/4 still won despite
            appearing first. Without !important the mobile drawer renders at 75%
            viewport width instead of the intended 256px. */}
        <SheetContent side="left" className="!w-64 border-r-0 bg-sidebar p-0 [&>button]:text-white">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarNav onNavigate={() => setMobileOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="flex min-h-screen flex-col lg:pl-64">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur supports-backdrop-filter:bg-background/80 sm:px-6">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="size-5" />
          </Button>

          <div className="flex flex-col leading-tight">
            <h1 className="text-sm font-semibold text-foreground sm:text-base">{activeItem.label}</h1>
            <p className="hidden text-xs text-muted-foreground sm:block">{activeItem.description}</p>
          </div>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <div className="relative hidden md:block">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search workflows, vendors, invoices…"
                className="h-9 w-64 bg-muted/60 pl-8 text-sm shadow-none focus-visible:bg-card xl:w-80"
              />
            </div>

            <Button variant="ghost" size="icon" className="relative text-muted-foreground hover:text-foreground" aria-label="Notifications">
              <Bell className="size-4.5" />
              <span className="absolute right-1.5 top-1.5 flex size-2 rounded-full bg-status-critical" />
            </Button>

            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger className="ml-1 flex items-center gap-2 rounded-full outline-none ring-ring focus-visible:ring-2">
                <Avatar className="size-8 border border-border">
                  <AvatarFallback className="bg-primary text-xs font-semibold text-primary-foreground">AM</AvatarFallback>
                </Avatar>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="flex flex-col">
                  <span className="text-sm font-medium">Alex Morgan</span>
                  <span className="text-xs font-normal text-muted-foreground">Finance Operations Lead</span>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Account settings</DropdownMenuItem>
                <DropdownMenuItem>API access tokens</DropdownMenuItem>
                <DropdownMenuItem>Notification preferences</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive">Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className={cn("flex-1 px-4 py-6 sm:px-6 lg:px-8")}>
          <div className="mx-auto w-full max-w-[1600px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
