"use client";

import type { ReactNode } from "react";

import type { Invoice } from "@/entities/invoice/model/types";
import { formatCurrency, formatDate, formatPercent } from "@/shared/lib/format";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { EmptyState } from "@/shared/ui/empty-state";
import { Spinner } from "@/shared/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

import { InvoiceStatusBadge } from "./invoice-status-badge";

export interface InvoiceDetailDialogProps {
  invoice?: Invoice;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  isLoading?: boolean;
  isError?: boolean;
  actions?: ReactNode;
}

function formatOptionalDate(value: string | null) {
  return value ? formatDate(value) : "Not set";
}

function DetailItem({ label, value }: Readonly<{ label: string; value: ReactNode }>) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <div className="text-sm font-medium">{value}</div>
    </div>
  );
}

export function InvoiceDetailDialog({
  invoice,
  open,
  onOpenChange,
  isLoading = false,
  isError = false,
  actions,
}: Readonly<InvoiceDetailDialogProps>) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{invoice ? `Invoice ${invoice.invoice_number}` : "Invoice details"}</DialogTitle>
          <DialogDescription>Review invoice details and download a PDF copy.</DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <Spinner />
          </div>
        ) : null}

        {isError ? (
          <EmptyState title="Unable to load invoice" description="Please close the popup and try again." />
        ) : null}

        {invoice ? (
          <div className="space-y-6">
            <div className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2 lg:grid-cols-4">
              <DetailItem label="Counterparty" value={invoice.counterparty ?? invoice.recipient_snapshot?.name ?? "-"} />
              <DetailItem label="Status" value={<InvoiceStatusBadge status={invoice.status} />} />
              <DetailItem label="Issue date" value={formatDate(invoice.issue_date)} />
              <DetailItem label="Tax event date" value={formatOptionalDate(invoice.tax_event_date)} />
              <DetailItem label="Due date" value={formatOptionalDate(invoice.due_date)} />
              <DetailItem label="Place of supply" value={invoice.place_of_supply ?? "-"} />
              <DetailItem label="Currency" value={invoice.currency} />
              <DetailItem label="Created" value={formatDate(invoice.created_at)} />
              <DetailItem label="Updated" value={formatDate(invoice.updated_at)} />
              <DetailItem label="Invoice ID" value={<span className="font-mono text-xs">{invoice.id}</span>} />
            </div>

            <div className="space-y-3">
              <div>
                <h3 className="text-sm font-medium">Line items</h3>
                <p className="text-xs text-muted-foreground">Detailed items, VAT, and totals for this invoice.</p>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Description</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead>Unit</TableHead>
                    <TableHead className="text-right">Unit price</TableHead>
                    <TableHead className="text-right">VAT</TableHead>
                    <TableHead className="text-right">Subtotal</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoice.items.map((item, index) => (
                    <TableRow key={`${item.description}-${index}`}>
                      <TableCell className="font-medium">{item.description}</TableCell>
                      <TableCell>{item.category ?? "-"}</TableCell>
                      <TableCell className="text-right">{item.quantity}</TableCell>
                      <TableCell>{item.unit_label}</TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(item.unit_price, invoice.currency)}
                      </TableCell>
                      <TableCell className="text-right">{formatPercent(item.vat_rate)}</TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(item.subtotal, invoice.currency)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(item.total, invoice.currency)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {invoice.notes ? (
              <div className="rounded-lg border p-4">
                <h3 className="text-sm font-medium">Notes</h3>
                <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{invoice.notes}</p>
              </div>
            ) : null}

            <div className="ml-auto w-full max-w-sm rounded-lg border bg-muted/30 p-4">
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">Subtotal</span>
                  <span className="font-medium">{formatCurrency(invoice.subtotal, invoice.currency)}</span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-muted-foreground">VAT</span>
                  <span className="font-medium">{formatCurrency(invoice.vat_total, invoice.currency)}</span>
                </div>
                <div className="flex items-center justify-between gap-4 border-t pt-2 text-base font-semibold">
                  <span>Total</span>
                  <span>{formatCurrency(invoice.total, invoice.currency)}</span>
                </div>
              </div>
            </div>

            {actions ? <DialogFooter>{actions}</DialogFooter> : null}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
