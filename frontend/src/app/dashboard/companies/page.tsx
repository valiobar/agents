import { CreateCompanyDialog } from "@/features/create-company/ui/create-company-dialog";
import { CompanyTable } from "@/widgets/company-table/ui/company-table";

export default function CompaniesPage() {
  return (
    <section className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Companies</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage the legal entities used to scope partners, agents, invoices, and documents.
          </p>
        </div>
        <CreateCompanyDialog />
      </div>

      <CompanyTable />
    </section>
  );
}
