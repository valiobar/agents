"use client";

import { Building2, Pencil } from "lucide-react";
import { useSession } from "next-auth/react";
import { useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import type { Company } from "@/entities/company/model/types";
import { UpdateCompanyForm } from "@/features/update-company/ui/update-company-form";
import { Button } from "@/shared/ui/button";
import { Badge } from "@/shared/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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

export function CompanyTable() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);

  if (companies.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        <span>Loading companies...</span>
      </div>
    );
  }

  if (companies.isError) {
    return (
      <EmptyState
        title="Unable to load companies"
        description="Please refresh the page and try again."
        action={
          <Button type="button" variant="outline" onClick={() => companies.refetch()}>
            Retry
          </Button>
        }
      />
    );
  }

  if (!companies.data?.length) {
    return (
      <EmptyState
        title="No companies yet"
        description="Create a company before assigning partners, agents, invoices, or documents."
      />
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Company</TableHead>
            <TableHead>Registration</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Contact</TableHead>
            <TableHead className="w-24 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {companies.data.map((company) => (
            <TableRow key={company.id}>
              <TableCell>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-md border bg-muted">
                    {company.logo_data_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={company.logo_data_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <Building2 className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 font-medium">
                      {company.name}
                      {company.is_default ? <Badge variant="secondary">Default</Badge> : null}
                    </div>
                    <p className="text-xs text-muted-foreground">{company.accountable_person}</p>
                  </div>
                </div>
              </TableCell>
              <TableCell>
                <div>{company.registration_number}</div>
                {company.vat_number ? (
                  <p className="text-xs text-muted-foreground">VAT {company.vat_number}</p>
                ) : null}
              </TableCell>
              <TableCell>
                {company.city}, {company.country}
              </TableCell>
              <TableCell>
                <div>{company.email ?? "No email"}</div>
                <p className="text-xs text-muted-foreground">{company.phone ?? "No phone"}</p>
              </TableCell>
              <TableCell className="text-right">
                <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedCompany(company)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Dialog open={Boolean(selectedCompany)} onOpenChange={(open) => !open && setSelectedCompany(null)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit company</DialogTitle>
            <DialogDescription>Update legal details used for company-scoped workflows.</DialogDescription>
          </DialogHeader>
          {selectedCompany ? (
            <UpdateCompanyForm
              company={selectedCompany}
              onSuccess={() => setSelectedCompany(null)}
              onCancel={() => setSelectedCompany(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
