"use client";

import { Badge } from "@/shared/ui/badge";
import { cn } from "@/shared/lib/cn";

import type { ExpenseCategory } from "../model/types";

const labels: Record<ExpenseCategory, string> = {
  office: "Office",
  travel: "Travel",
  meals: "Meals",
  software: "Software",
  rent: "Rent",
  utilities: "Utilities",
  professional_services: "Professional services",
  tax: "Tax",
  payroll: "Payroll",
  other: "Other",
};

export function CategoryBadge({
  category,
  className,
}: Readonly<{ category: ExpenseCategory; className?: string }>) {
  return (
    <Badge variant="secondary" className={cn("whitespace-nowrap", className)}>
      {labels[category]}
    </Badge>
  );
}
