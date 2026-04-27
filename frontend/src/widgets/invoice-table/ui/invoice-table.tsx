"use client";

import { useSession } from "next-auth/react";
import { useEffect, useMemo, useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { useInvoice, useInvoices } from "@/entities/invoice/api/queries";
import { InvoiceDetailDialog } from "@/entities/invoice/ui/invoice-detail-dialog";
import { InvoiceStatusBadge } from "@/entities/invoice/ui/invoice-status-badge";
import { PartnerSelect } from "@/entities/partner/ui/partner-select";
import { DownloadInvoicePdfButton } from "@/features/download-invoice-pdf/ui/download-invoice-pdf-button";
import { useInvoiceFiltersStore } from "@/shared/store/invoice-filters-store";
import { formatCurrency, formatDate } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

import type { InvoiceStatus } from "@/entities/invoice/model/types";

const STATUSES: Array<{ label: string; value: InvoiceStatus }> = [
  { label: "Draft", value: "draft" },
  { label: "Sent", value: "sent" },
  { label: "Paid", value: "paid" },
  { label: "Overdue", value: "overdue" },
  { label: "Cancelled", value: "cancelled" },
];
const ANY_STATUS = "any";

export function InvoiceTable() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string | null>(null);

  const {
    companyId,
    partnerId,
    status,
    dateRange,
    counterparty,
    category,
    amountMin,
    amountMax,
    setCompanyId,
    setPartnerId,
    setStatus,
    setDateRange,
    setCounterparty,
    setCategory,
    setAmountMin,
    setAmountMax,
    reset,
  } = useInvoiceFiltersStore();

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  useEffect(() => {
    if (!companyId && defaultCompanyId) {
      setCompanyId(defaultCompanyId);
    }
  }, [companyId, defaultCompanyId, setCompanyId]);

  const invoices = useInvoices(session?.accessToken, {
    company_id: companyId || undefined,
    partner_id: partnerId ?? undefined,
    status: status ?? undefined,
    date_from: dateRange?.from || undefined,
    date_to: dateRange?.to || undefined,
    counterparty: counterparty || undefined,
    category: category || undefined,
    amount_min: amountMin || undefined,
    amount_max: amountMax || undefined,
    limit: 50,
    offset: 0,
  });
  const selectedInvoice = useInvoice(selectedInvoiceId ?? "", session?.accessToken);

  const content = (() => {
    if (companies.isLoading || invoices.isLoading) {
      return (
        <div className="flex items-center justify-center py-10">
          <Spinner />
        </div>
      );
    }

    if (!companies.data?.length) {
      return (
        <EmptyState
          title="Create a company first"
          description="Invoices are scoped to a company. Create a company before adding invoices."
        />
      );
    }

    if (invoices.isError) {
      return (
        <EmptyState
          title="Unable to load invoices"
          description="Please try again in a moment."
          action={
            <Button type="button" variant="outline" onClick={() => invoices.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }

    if (!invoices.data?.length) {
      return (
        <EmptyState title="No invoices yet" description="Create your first invoice to see it listed here." />
      );
    }

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Invoice</TableHead>
            <TableHead>Counterparty</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Total</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.data.map((inv) => (
            <TableRow
              key={inv.id}
              role="button"
              tabIndex={0}
              className="cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Open invoice ${inv.invoice_number}`}
              onClick={() => setSelectedInvoiceId(inv.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedInvoiceId(inv.id);
                }
              }}
            >
              <TableCell className="font-medium">{inv.invoice_number}</TableCell>
              <TableCell>{inv.counterparty ?? inv.recipient_snapshot?.name ?? "-"}</TableCell>
              <TableCell>{formatDate(inv.issue_date)}</TableCell>
              <TableCell>{formatCurrency(inv.total, inv.currency)}</TableCell>
              <TableCell>
                <InvoiceStatusBadge status={inv.status} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  })();

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="lg:col-span-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Company</p>
            <Select value={companyId} onValueChange={setCompanyId} disabled={companies.isLoading}>
              <SelectTrigger>
                <SelectValue placeholder="Select company" />
              </SelectTrigger>
              <SelectContent>
                {companies.data?.map((company) => (
                  <SelectItem key={company.id} value={company.id}>
                    {company.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Partner</p>
            <div className="flex gap-2">
              <div className="min-w-0 flex-1">
                <PartnerSelect
                  companyId={companyId}
                  value={partnerId}
                  onChange={setPartnerId}
                  placeholder="Any partner"
                  disabled={!companyId}
                />
              </div>
              <Button type="button" variant="outline" onClick={() => setPartnerId(null)} disabled={!partnerId}>
                Clear
              </Button>
            </div>
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Status</p>
            <Select
              value={status ?? ANY_STATUS}
              onValueChange={(v) =>
                setStatus(v === ANY_STATUS ? null : (v as InvoiceStatus))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY_STATUS}>Any</SelectItem>
                {STATUSES.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">From</p>
            <Input
              type="date"
              value={dateRange?.from ?? ""}
              onChange={(e) =>
                setDateRange(
                  e.target.value
                    ? { from: e.target.value, to: dateRange?.to ?? e.target.value }
                    : null,
                )
              }
            />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">To</p>
            <Input
              type="date"
              value={dateRange?.to ?? ""}
              onChange={(e) =>
                setDateRange(
                  e.target.value
                    ? { from: dateRange?.from ?? e.target.value, to: e.target.value }
                    : null,
                )
              }
            />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Counterparty</p>
            <Input
              placeholder="Search…"
              value={counterparty}
              onChange={(e) => setCounterparty(e.target.value)}
            />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Category</p>
            <Input placeholder="services" value={category} onChange={(e) => setCategory(e.target.value)} />
          </div>

          <div className="lg:col-span-1">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Amount</p>
            <div className="flex gap-2">
              <Input
                placeholder="Min"
                inputMode="decimal"
                value={amountMin}
                onChange={(e) => setAmountMin(e.target.value)}
              />
              <Input
                placeholder="Max"
                inputMode="decimal"
                value={amountMax}
                onChange={(e) => setAmountMax(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          <Button type="button" variant="outline" onClick={reset}>
            Reset
          </Button>
        </div>
      </div>

      {content}
      <InvoiceDetailDialog
        open={Boolean(selectedInvoiceId)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedInvoiceId(null);
          }
        }}
        invoice={selectedInvoice.data}
        isLoading={selectedInvoice.isLoading}
        isError={selectedInvoice.isError}
        actions={
          selectedInvoice.data ? <DownloadInvoicePdfButton invoice={selectedInvoice.data} /> : null
        }
      />
    </div>
  );
}

