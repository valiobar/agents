import { create } from "zustand";

import type { ExpenseCategory } from "@/entities/expense/model/types";

type DateRange = { from: string; to: string };

interface ExpenseFiltersStore {
  category: ExpenseCategory | null;
  dateRange: DateRange | null;
  counterparty: string;
  deductible: "all" | "deductible" | "non_deductible";
  amountMin: string;
  amountMax: string;
  setCategory: (category: ExpenseCategory | null) => void;
  setDateRange: (range: DateRange | null) => void;
  setCounterparty: (value: string) => void;
  setDeductible: (value: ExpenseFiltersStore["deductible"]) => void;
  setAmountMin: (value: string) => void;
  setAmountMax: (value: string) => void;
  reset: () => void;
}

export const useExpenseFiltersStore = create<ExpenseFiltersStore>((set) => ({
  category: null,
  dateRange: null,
  counterparty: "",
  deductible: "all",
  amountMin: "",
  amountMax: "",
  setCategory: (category) => set({ category }),
  setDateRange: (dateRange) => set({ dateRange }),
  setCounterparty: (counterparty) => set({ counterparty }),
  setDeductible: (deductible) => set({ deductible }),
  setAmountMin: (amountMin) => set({ amountMin }),
  setAmountMax: (amountMax) => set({ amountMax }),
  reset: () =>
    set({
      category: null,
      dateRange: null,
      counterparty: "",
      deductible: "all",
      amountMin: "",
      amountMax: "",
    }),
}));

