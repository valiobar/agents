import { useMutation, useQueryClient } from "@tanstack/react-query";

import { inventoryKeys } from "@/entities/inventory/model/query-keys";
import type { InventoryItem } from "@/entities/inventory/model/types";
import { apiClient } from "@/shared/api/client";

import type { CreateInventoryItemInput, UpdateInventoryItemInput } from "../model/schema";

export function useCreateInventoryItem(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateInventoryItemInput) =>
      apiClient.post<InventoryItem>("/inventory/items", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
}

export function useUpdateInventoryItem(itemId: string, companyId: string, token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: UpdateInventoryItemInput) =>
      apiClient.patch<InventoryItem>(`/inventory/items/${itemId}`, input, {
        token,
        params: { company_id: companyId },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
}
