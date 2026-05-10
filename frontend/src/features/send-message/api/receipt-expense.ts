import type {
  ConfirmInventoryImportForExpenseResponse,
  DocumentIntakeResponse,
  ExpenseDraft,
  ExpenseDraftRequestSourceDocumentType,
  ExpenseDraftResponse,
} from "@/entities/expense/model/types";
import type { ImportPreviewLine, InventoryImportPreview } from "@/entities/inventory/model/types";
import { apiClient } from "@/shared/api/client";

import type { ConfirmExtractedExpenseResponse } from "../model/receipt-expense-schema";

export interface CreateExpenseDraftInput {
  agentId: string;
  file: File;
  sourceDocumentType: ExpenseDraftRequestSourceDocumentType;
  token: string;
}

export interface CreateDocumentIntakeInput {
  agentId: string;
  file: File;
  requestedType: ExpenseDraftRequestSourceDocumentType;
  token: string;
}

export async function createDocumentIntake(input: CreateDocumentIntakeInput): Promise<DocumentIntakeResponse> {
  const formData = new FormData();
  formData.set("file", input.file);
  formData.set("requested_type", input.requestedType);

  return apiClient.post<DocumentIntakeResponse>(`/agents/${input.agentId}/document-intake`, formData, {
    token: input.token,
  });
}

export async function createExpenseDraft(input: CreateExpenseDraftInput): Promise<ExpenseDraftResponse> {
  const formData = new FormData();
  formData.set("file", input.file);
  formData.set("source_document_type", input.sourceDocumentType);

  return apiClient.post<ExpenseDraftResponse>(`/agents/${input.agentId}/expense-drafts`, formData, {
    token: input.token,
  });
}

export interface ConfirmInventoryImportForExpenseInput {
  agentId: string;
  previewId: string;
  draft: ExpenseDraft;
  token: string;
}

export async function confirmInventoryImportForExpense(
  input: ConfirmInventoryImportForExpenseInput,
): Promise<ConfirmInventoryImportForExpenseResponse> {
  return apiClient.post<ConfirmInventoryImportForExpenseResponse>(
    `/agents/${input.agentId}/document-intake/supplier-invoice/inventory-imports/confirm`,
    {
      preview_id: input.previewId,
      draft: input.draft,
    },
    { token: input.token },
  );
}

export interface UpdateInventoryImportPreviewLinesInput {
  previewId: string;
  lines: ImportPreviewLine[];
  token: string;
}

export async function updateInventoryImportPreviewLines(
  input: UpdateInventoryImportPreviewLinesInput,
): Promise<InventoryImportPreview> {
  return apiClient.patch<InventoryImportPreview>(
    `/inventory/import-previews/${input.previewId}`,
    { lines: input.lines },
    { token: input.token },
  );
}

export interface ConfirmExtractedExpenseInput {
  agentId: string;
  draft: ExpenseDraft;
  token: string;
}

export async function confirmExtractedExpense(
  input: ConfirmExtractedExpenseInput,
): Promise<ConfirmExtractedExpenseResponse> {
  return apiClient.post<ConfirmExtractedExpenseResponse>(
    `/agents/${input.agentId}/expenses/confirm`,
    {
      ...input.draft,
      confirmed: true,
    },
    { token: input.token },
  );
}

