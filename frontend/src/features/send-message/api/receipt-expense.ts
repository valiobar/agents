import type {
  ExpenseDraft,
  ExpenseDraftRequestSourceDocumentType,
  ExpenseDraftResponse,
} from "@/entities/expense/model/types";
import { apiClient } from "@/shared/api/client";

import type { ConfirmExtractedExpenseResponse } from "../model/receipt-expense-schema";

export interface CreateExpenseDraftInput {
  agentId: string;
  file: File;
  sourceDocumentType: ExpenseDraftRequestSourceDocumentType;
  token: string;
}

export async function createExpenseDraft(input: CreateExpenseDraftInput): Promise<ExpenseDraftResponse> {
  const formData = new FormData();
  formData.set("file", input.file);
  formData.set("source_document_type", input.sourceDocumentType);

  return apiClient.post<ExpenseDraftResponse>(`/agents/${input.agentId}/expense-drafts`, formData, {
    token: input.token,
  });
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

