import { PartnerTable } from "@/widgets/partner-table/ui/partner-table";

export default function PartnersPage() {
  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Partners</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage company-scoped clients, suppliers, and other counterparties.
        </p>
      </div>

      <PartnerTable />
    </section>
  );
}
