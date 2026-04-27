import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Invoice } from "@/entities/invoice/model/types";
import { invoiceKeys } from "@/entities/invoice/model/query-keys";
import { apiClient } from "@/shared/api/client";

import type { CreateInvoiceInput } from "../model/schema";

export function useCreateInvoice(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateInvoiceInput) => apiClient.post<Invoice>("/invoices", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: invoiceKeys.all });
    },
  });
}

