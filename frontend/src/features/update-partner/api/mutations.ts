import { useMutation, useQueryClient } from "@tanstack/react-query";

import { partnerKeys } from "@/entities/partner/model/query-keys";
import type { Partner } from "@/entities/partner/model/types";
import { apiClient } from "@/shared/api/client";

import type { UpdatePartnerInput } from "../model/schema";

interface UpdatePartnerVariables {
  partnerId: string;
  companyId: string;
  input: UpdatePartnerInput;
}

export function useUpdatePartner(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ partnerId, companyId, input }: UpdatePartnerVariables) =>
      apiClient.patch<Partner>(`/partners/${partnerId}`, input, {
        token,
        params: { company_id: companyId },
      }),
    onSuccess: async (partner) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
        queryClient.invalidateQueries({
          queryKey: partnerKeys.detail(partner.id, partner.company_id),
        }),
      ]);
    },
  });
}

export function useDeletePartner(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ partnerId, companyId }: { partnerId: string; companyId: string }) =>
      apiClient.delete(`/partners/${partnerId}`, { token, params: { company_id: companyId } }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: partnerKeys.all });
    },
  });
}
