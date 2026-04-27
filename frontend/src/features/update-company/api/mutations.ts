import { useMutation, useQueryClient } from "@tanstack/react-query";

import { companyKeys } from "@/entities/company/model/query-keys";
import type { Company } from "@/entities/company/model/types";
import { apiClient } from "@/shared/api/client";

import type { UpdateCompanyInput } from "../model/schema";

interface UpdateCompanyVariables {
  companyId: string;
  input: UpdateCompanyInput;
}

export function useUpdateCompany(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ companyId, input }: UpdateCompanyVariables) =>
      apiClient.patch<Company>(`/companies/${companyId}`, input, { token }),
    onSuccess: async (company) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: companyKeys.all }),
        queryClient.invalidateQueries({ queryKey: companyKeys.detail(company.id) }),
      ]);
    },
  });
}

export function useDeleteCompany(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (companyId: string) => apiClient.delete(`/companies/${companyId}`, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: companyKeys.all });
    },
  });
}
