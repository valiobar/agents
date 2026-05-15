import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import { companyKeys, type CompanyListParams } from "../model/query-keys";
import type { Company, CompanyListResponse } from "../model/types";

const DEFAULT_COMPANY_LIST_PARAMS: CompanyListParams = { limit: 50, offset: 0 };

export function useCompanies(
  token?: string | null,
  params: CompanyListParams = DEFAULT_COMPANY_LIST_PARAMS,
) {
  return useQuery({
    queryKey: companyKeys.list(params),
    enabled: Boolean(token),
    queryFn: () => apiClient.get<CompanyListResponse>("/companies", { token, params }),
    select: (response) => response.items,
  });
}

export function useCompany(companyId: string, token?: string | null) {
  return useQuery({
    queryKey: companyKeys.detail(companyId),
    enabled: Boolean(token && companyId),
    queryFn: () => apiClient.get<Company>(`/companies/${companyId}`, { token }),
  });
}
