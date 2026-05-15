import { apiClient } from "@/shared/api/client";

import type {
  ConfirmSalesInvoiceInput,
  ConfirmSalesInvoiceInventoryInput,
  CreateSalesInvoiceInventoryPreviewInput,
  SalesInvoiceCreatedResponse,
  SalesInvoiceInventoryReview,
  SalesInvoiceReview,
} from "../model/sales-invoice-workflow-schema";

export async function createSalesInvoiceInventoryPreview(
  input: CreateSalesInvoiceInventoryPreviewInput & { agentId: string; token: string },
): Promise<SalesInvoiceInventoryReview> {
  return apiClient.post<SalesInvoiceInventoryReview>(
    `/agents/${input.agentId}/invoice-workflows/sales-inventory/preview`,
    input.payload,
    { token: input.token },
  );
}

export async function confirmSalesInvoiceInventoryReview(
  input: ConfirmSalesInvoiceInventoryInput & { agentId: string; token: string },
): Promise<SalesInvoiceReview> {
  return apiClient.post<SalesInvoiceReview>(
    `/agents/${input.agentId}/invoice-workflows/sales-inventory/inventory/confirm`,
    input.payload,
    { token: input.token },
  );
}

export async function confirmSalesInvoiceDraft(
  input: ConfirmSalesInvoiceInput & { agentId: string; token: string },
): Promise<SalesInvoiceCreatedResponse> {
  return apiClient.post<SalesInvoiceCreatedResponse>(
    `/agents/${input.agentId}/invoice-workflows/sales-inventory/invoice/confirm`,
    { invoice_draft: input.invoiceDraft, confirmed: true },
    { token: input.token },
  );
}
