"use client";

import { Badge } from "@/shared/ui/badge";
import { cn } from "@/shared/lib/cn";

import type { InvoiceStatus } from "../model/types";

const styles: Record<InvoiceStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-muted text-foreground border-transparent" },
  sent: { label: "Sent", className: "bg-blue-600 text-white border-transparent" },
  paid: { label: "Paid", className: "bg-emerald-600 text-white border-transparent" },
  overdue: { label: "Overdue", className: "bg-red-600 text-white border-transparent" },
  cancelled: { label: "Cancelled", className: "bg-zinc-500 text-white border-transparent" },
};

export function InvoiceStatusBadge({ status, className }: { status: InvoiceStatus; className?: string }) {
  const s = styles[status];
  return <Badge className={cn(s.className, className)}>{s.label}</Badge>;
}

