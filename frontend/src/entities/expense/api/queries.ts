import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import { expenseKeys, type ExpenseListParams } from "../model/query-keys";
import type { Expense, ExpenseListResponse } from "../model/types";

const DEFAULT_EXPENSE_LIST_PARAMS: ExpenseListParams = { limit: 50, offset: 0 };

export function useExpenses(
  token?: string | null,
  params: ExpenseListParams = DEFAULT_EXPENSE_LIST_PARAMS,
) {
  return useQuery({
    queryKey: expenseKeys.list(params),
    enabled: Boolean(token),
    queryFn: () => apiClient.get<ExpenseListResponse>("/expenses", { token, params }),
    select: (response) => response.items,
  });
}

export function useExpense(expenseId: string, token?: string | null) {
  return useQuery({
    queryKey: expenseKeys.detail(expenseId),
    enabled: Boolean(token && expenseId),
    queryFn: () => apiClient.get<Expense>(`/expenses/${expenseId}`, { token }),
  });
}
