import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";

import type { DocumentResponse } from "../model/types";
import type { UploadDocumentInput } from "../model/schema";

export interface DocumentListParams {
  [key: string]: string | number | boolean | null | undefined;
  company_id?: string;
  limit?: number;
  offset?: number;
}

export const documentKeys = {
  all: ["documents"] as const,
  list: (params: DocumentListParams = {}) => [...documentKeys.all, "list", params] as const,
};

export function useDocuments(
  token?: string | null,
  params: DocumentListParams = { limit: 50, offset: 0 },
) {
  return useQuery({
    queryKey: documentKeys.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () =>
      apiClient.get<DocumentResponse[]>("/documents", {
        token,
        params,
      }),
  });
}

export function useUploadDocument(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, company_id }: UploadDocumentInput) => {
      const formData = new FormData();
      formData.set("file", file);
      formData.set("company_id", company_id);
      return apiClient.post<DocumentResponse>("/documents", formData, { token });
    },
    onSuccess: (_document, input) => {
      queryClient.invalidateQueries({ queryKey: documentKeys.list({ company_id: input.company_id }) });
      queryClient.invalidateQueries({ queryKey: documentKeys.all });
    },
  });
}

export function getDocumentUploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session expired. Sign in again before uploading documents.";
    }
    if (error.status === 413) {
      return "The selected file is too large. Upload a file up to 10 MB.";
    }
    if (error.status === 415) {
      return "Unsupported file type. Upload a PDF, text, or Markdown file.";
    }
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Upload failed. Please try again.";
}
