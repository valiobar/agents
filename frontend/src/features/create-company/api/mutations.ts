import { useMutation, useQueryClient } from "@tanstack/react-query";

import { companyKeys } from "@/entities/company/model/query-keys";
import type { Company } from "@/entities/company/model/types";
import { apiClient } from "@/shared/api/client";

import type { CompanyInput } from "../model/schema";

export function useCreateCompany(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CompanyInput) => apiClient.post<Company>("/companies", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: companyKeys.all });
    },
  });
}
