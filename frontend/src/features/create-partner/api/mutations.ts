import { useMutation, useQueryClient } from "@tanstack/react-query";

import { partnerKeys } from "@/entities/partner/model/query-keys";
import type { Partner } from "@/entities/partner/model/types";
import { apiClient } from "@/shared/api/client";

import type { PartnerInput } from "../model/schema";

export function useCreatePartner(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: PartnerInput) => apiClient.post<Partner>("/partners", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: partnerKeys.all });
    },
  });
}
