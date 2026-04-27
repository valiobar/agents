"use client";

import { Pencil } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useMemo, useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { usePartners } from "@/entities/partner/api/queries";
import type { Partner, PartnerKind } from "@/entities/partner/model/types";
import { CreatePartnerDialog } from "@/features/create-partner/ui/create-partner-dialog";
import { UpdatePartnerForm } from "@/features/update-partner/ui/update-partner-form";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
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

const ANY_KIND = "any";
const PARTNER_KINDS: Array<{ label: string; value: PartnerKind }> = [
  { label: "Client", value: "client" },
  { label: "Supplier", value: "supplier" },
  { label: "Both", value: "both" },
  { label: "Other", value: "other" },
];

export function PartnerTable() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [kind, setKind] = useState<PartnerKind | null>(null);
  const [query, setQuery] = useState("");
  const [selectedPartner, setSelectedPartner] = useState<Partner | null>(null);

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  useEffect(() => {
    if (!selectedCompanyId && defaultCompanyId) {
      setSelectedCompanyId(defaultCompanyId);
    }
  }, [defaultCompanyId, selectedCompanyId]);

  const partners = usePartners(session?.accessToken, {
    company_id: selectedCompanyId || undefined,
    kind: kind ?? undefined,
    query: query || undefined,
    limit: 50,
    offset: 0,
  });

  if (companies.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        <span>Loading companies...</span>
      </div>
    );
  }

  if (!companies.data?.length) {
    return (
      <EmptyState
        title="Create a company first"
        description="Partners are scoped to a company, so add a company before creating partners."
      />
    );
  }

  const content = (() => {
    if (!selectedCompanyId || partners.isLoading) {
      return (
        <div className="flex items-center justify-center py-10">
          <Spinner />
        </div>
      );
    }

    if (partners.isError) {
      return (
        <EmptyState
          title="Unable to load partners"
          description="Please try again in a moment."
          action={
            <Button type="button" variant="outline" onClick={() => partners.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }

    if (!partners.data?.length) {
      return (
        <EmptyState
          title="No partners found"
          description="Create a partner or adjust the current filters."
        />
      );
    }

    return (
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Partner</TableHead>
            <TableHead>Kind</TableHead>
            <TableHead>Registration</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Contact</TableHead>
            <TableHead className="w-24 text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {partners.data.map((partner) => (
            <TableRow key={partner.id}>
              <TableCell>
                <div className="font-medium">{partner.name}</div>
                <p className="text-xs text-muted-foreground">{partner.accountable_person}</p>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{partner.kind}</Badge>
              </TableCell>
              <TableCell>
                <div>{partner.registration_number}</div>
                {partner.vat_number ? (
                  <p className="text-xs text-muted-foreground">VAT {partner.vat_number}</p>
                ) : null}
              </TableCell>
              <TableCell>
                {partner.city}, {partner.country}
              </TableCell>
              <TableCell>
                <div>{partner.email ?? "No email"}</div>
                <p className="text-xs text-muted-foreground">{partner.phone ?? "No phone"}</p>
              </TableCell>
              <TableCell className="text-right">
                <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedPartner(partner)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </Button>
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
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1.5fr)_auto]">
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Company</p>
            <Select value={selectedCompanyId} onValueChange={setSelectedCompanyId}>
              <SelectTrigger>
                <SelectValue placeholder="Select company" />
              </SelectTrigger>
              <SelectContent>
                {companies.data.map((company) => (
                  <SelectItem key={company.id} value={company.id}>
                    {company.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Kind</p>
            <Select value={kind ?? ANY_KIND} onValueChange={(value) => setKind(value === ANY_KIND ? null : (value as PartnerKind))}>
              <SelectTrigger>
                <SelectValue placeholder="Any" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY_KIND}>Any</SelectItem>
                {PARTNER_KINDS.map((partnerKind) => (
                  <SelectItem key={partnerKind.value} value={partnerKind.value}>
                    {partnerKind.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Search</p>
            <Input placeholder="Name or registration" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>

          <div className="flex items-end">
            <CreatePartnerDialog defaultCompanyId={selectedCompanyId} />
          </div>
        </div>
      </div>

      {content}

      <Dialog open={Boolean(selectedPartner)} onOpenChange={(open) => !open && setSelectedPartner(null)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit partner</DialogTitle>
            <DialogDescription>Update partner details used for invoices and company reports.</DialogDescription>
          </DialogHeader>
          {selectedPartner ? (
            <UpdatePartnerForm
              partner={selectedPartner}
              onSuccess={() => setSelectedPartner(null)}
              onCancel={() => setSelectedPartner(null)}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
