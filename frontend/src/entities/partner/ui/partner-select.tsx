"use client";

import { useSession } from "next-auth/react";

import { usePartners } from "@/entities/partner/api/queries";
import type { PartnerKind } from "@/entities/partner/model/types";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";

interface PartnerSelectProps {
  companyId?: string | null;
  value?: string | null;
  onChange: (partnerId: string) => void;
  kind?: PartnerKind;
  placeholder?: string;
  disabled?: boolean;
}

export function PartnerSelect({
  companyId,
  value,
  onChange,
  kind = "client",
  placeholder = "Select partner",
  disabled = false,
}: Readonly<PartnerSelectProps>) {
  const { data: session } = useSession();
  const partners = usePartners(session?.accessToken, {
    company_id: companyId ?? undefined,
    kind,
    limit: 50,
    offset: 0,
  });

  return (
    <Select
      value={value ?? ""}
      onValueChange={onChange}
      disabled={disabled || !companyId || partners.isLoading}
    >
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {partners.data?.map((partner) => (
          <SelectItem key={partner.id} value={partner.id}>
            {partner.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
