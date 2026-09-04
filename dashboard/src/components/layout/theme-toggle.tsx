"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { buttonVariants } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid rendering an icon that depends on the resolved theme until after
  // hydration -- the server has no theme cookie/localStorage to read from.
  useEffect(() => setMounted(true), []);

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <Tooltip>
      <TooltipTrigger
        aria-label="Toggle theme"
        onClick={() => setTheme(isDark ? "light" : "dark")}
        className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "text-muted-foreground hover:text-foreground")}
      >
        {mounted && isDark ? <Sun className="size-4.5" /> : <Moon className="size-4.5" />}
      </TooltipTrigger>
      <TooltipContent>{isDark ? "Switch to light mode" : "Switch to dark mode"}</TooltipContent>
    </Tooltip>
  );
}
