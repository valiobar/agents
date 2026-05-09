import { useMutation, useQueryClient } from "@tanstack/react-query";

import { inventoryKeys } from "@/entities/inventory/model/query-keys";
import type { InventoryImportPreview, InventoryImportResult } from "@/entities/inventory/model/types";
import { apiClient } from "@/shared/api/client";

export function useConfirmImportPreview(previewId: string, token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiClient.post<InventoryImportResult>(
        `/inventory/import-previews/${previewId}/confirm`,
        {},
        { token },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
}

export function useCancelImportPreview(previewId: string, token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiClient.post<InventoryImportPreview>(
        `/inventory/import-previews/${previewId}/cancel`,
        {},
        { token },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
}
