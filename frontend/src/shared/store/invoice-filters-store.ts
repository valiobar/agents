import { create } from "zustand";

import type { InvoiceStatus } from "@/entities/invoice/model/types";

type DateRange = { from: string; to: string };

interface InvoiceFiltersStore {
  companyId: string;
  partnerId: string | null;
  status: InvoiceStatus | null;
  dateRange: DateRange | null;
  counterparty: string;
  category: string;
  amountMin: string;
  amountMax: string;
  setCompanyId: (value: string) => void;
  setPartnerId: (value: string | null) => void;
  setStatus: (status: InvoiceStatus | null) => void;
  setDateRange: (range: DateRange | null) => void;
  setCounterparty: (value: string) => void;
  setCategory: (value: string) => void;
  setAmountMin: (value: string) => void;
  setAmountMax: (value: string) => void;
  reset: () => void;
}

export const useInvoiceFiltersStore = create<InvoiceFiltersStore>((set) => ({
  companyId: "",
  partnerId: null,
  status: null,
  dateRange: null,
  counterparty: "",
  category: "",
  amountMin: "",
  amountMax: "",
  setCompanyId: (companyId) => set({ companyId, partnerId: null }),
  setPartnerId: (partnerId) => set({ partnerId }),
  setStatus: (status) => set({ status }),
  setDateRange: (dateRange) => set({ dateRange }),
  setCounterparty: (counterparty) => set({ counterparty }),
  setCategory: (category) => set({ category }),
  setAmountMin: (amountMin) => set({ amountMin }),
  setAmountMax: (amountMax) => set({ amountMax }),
  reset: () =>
    set({
      partnerId: null,
      status: null,
      dateRange: null,
      counterparty: "",
      category: "",
      amountMin: "",
      amountMax: "",
    }),
}));

