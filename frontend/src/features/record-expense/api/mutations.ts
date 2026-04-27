import { useMutation, useQueryClient } from "@tanstack/react-query";

import { expenseKeys } from "@/entities/expense/model/query-keys";
import type { Expense } from "@/entities/expense/model/types";
import { apiClient } from "@/shared/api/client";

import type { RecordExpenseInput } from "../model/schema";

export function useRecordExpense(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: RecordExpenseInput) => apiClient.post<Expense>("/expenses", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: expenseKeys.all });
    },
  });
}

