import { CreateInvoiceDialog } from "@/features/create-invoice/ui/create-invoice-dialog";
import { InvoiceTable } from "@/widgets/invoice-table/ui/invoice-table";

export default function InvoicesPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Invoices</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create invoices and track totals and statuses.
          </p>
        </div>
        <CreateInvoiceDialog />
      </div>

      <InvoiceTable />
    </section>
  );
}

