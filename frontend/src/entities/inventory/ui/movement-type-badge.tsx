"use client";

import { cn } from "@/shared/lib/cn";

import type { MovementType } from "../model/types";

interface MovementTypeBadgeProps {
  type: MovementType;
  className?: string;
}

const MOVEMENT_LABELS: Record<
  MovementType,
  { label: string; className: string }
> = {
  receipt: {
    label: "Receipt",
    className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  },
  issue: {
    label: "Issue",
    className: "bg-orange-500/10 text-orange-700 dark:text-orange-300",
  },
  adjustment: {
    label: "Adjustment",
    className: "bg-blue-500/10 text-blue-700 dark:text-blue-300",
  },
  transfer_in: {
    label: "Transfer In",
    className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  },
  transfer_out: {
    label: "Transfer Out",
    className: "bg-orange-500/10 text-orange-700 dark:text-orange-300",
  },
  return: {
    label: "Return",
    className: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
  },
};

export function MovementTypeBadge({
  type,
  className,
}: Readonly<MovementTypeBadgeProps>) {
  const config = MOVEMENT_LABELS[type];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        config.className,
        className,
      )}
    >
      {config.label}
    </span>
  );
}

