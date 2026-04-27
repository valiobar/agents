import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import { invoiceKeys, type InvoiceListParams } from "../model/query-keys";
import type { Invoice } from "../model/types";

const DEFAULT_INVOICE_LIST_PARAMS: InvoiceListParams = { limit: 50, offset: 0 };

export function useInvoices(
  token?: string | null,
  params: InvoiceListParams = DEFAULT_INVOICE_LIST_PARAMS,
) {
  return useQuery({
    queryKey: invoiceKeys.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () => apiClient.get<Invoice[]>("/invoices", { token, params }),
  });
}

export function useInvoice(invoiceId: string, token?: string | null) {
  return useQuery({
    queryKey: invoiceKeys.detail(invoiceId),
    enabled: Boolean(token && invoiceId),
    queryFn: () => apiClient.get<Invoice>(`/invoices/${invoiceId}`, { token }),
  });
}
