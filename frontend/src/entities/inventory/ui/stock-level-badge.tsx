"use client";

import { cn } from "@/shared/lib/cn";

interface StockLevelBadgeProps {
  available: string;
  reorderPoint: string | null;
}

export function StockLevelBadge({
  available,
  reorderPoint,
}: Readonly<StockLevelBadgeProps>) {
  const qty = Number.parseFloat(available);
  const threshold = reorderPoint ? Number.parseFloat(reorderPoint) : null;
  const isLow = threshold !== null && qty <= threshold;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        isLow
          ? "bg-destructive/10 text-destructive"
          : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          isLow ? "bg-destructive" : "bg-emerald-500",
        )}
      />
      {available} {isLow && "(low)"}
    </span>
  );
}

