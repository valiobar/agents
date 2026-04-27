import type { InvoiceStatus } from "./types";

export interface InvoiceListParams {
  [key: string]: string | number | boolean | null | undefined;
  status?: InvoiceStatus;
  company_id?: string;
  partner_id?: string;
  date_from?: string;
  date_to?: string;
  counterparty?: string;
  amount_min?: string;
  amount_max?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

export const invoiceKeys = {
  all: ["invoices"] as const,
  list: (params: InvoiceListParams = {}) => [...invoiceKeys.all, "list", params] as const,
  detail: (invoiceId: string) => [...invoiceKeys.all, "detail", invoiceId] as const,
};

