import type { ExpenseCategory } from "./types";

export interface ExpenseListParams {
  [key: string]: string | number | boolean | null | undefined;
  category?: ExpenseCategory;
  counterparty?: string;
  date_from?: string;
  date_to?: string;
  deductible?: boolean;
  amount_min?: string;
  amount_max?: string;
  limit?: number;
  offset?: number;
}

export const expenseKeys = {
  all: ["expenses"] as const,
  list: (params: ExpenseListParams = {}) => [...expenseKeys.all, "list", params] as const,
  detail: (expenseId: string) => [...expenseKeys.all, "detail", expenseId] as const,
};

