import { useMutation, useQueryClient } from "@tanstack/react-query";

import { inventoryKeys } from "@/entities/inventory/model/query-keys";
import type { StockMovement } from "@/entities/inventory/model/types";
import { apiClient } from "@/shared/api/client";

import type { RecordStockMovementInput } from "../model/schema";

export function useRecordStockMovement(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: RecordStockMovementInput) =>
      apiClient.post<StockMovement>("/inventory/movements", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
    },
  });
}
