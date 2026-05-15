import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import { partnerKeys, type PartnerListParams } from "../model/query-keys";
import type { Partner, PartnerListResponse } from "../model/types";

const DEFAULT_PARTNER_LIST_PARAMS: PartnerListParams = { limit: 50, offset: 0 };

export function usePartners(
  token?: string | null,
  params: PartnerListParams = DEFAULT_PARTNER_LIST_PARAMS,
) {
  return useQuery({
    queryKey: partnerKeys.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () => apiClient.get<PartnerListResponse>("/partners", { token, params }),
    select: (response) => response.items,
  });
}

export function usePartner(partnerId: string, companyId: string, token?: string | null) {
  return useQuery({
    queryKey: partnerKeys.detail(partnerId, companyId),
    enabled: Boolean(token && partnerId && companyId),
    queryFn: () =>
      apiClient.get<Partner>(`/partners/${partnerId}`, { token, params: { company_id: companyId } }),
  });
}
