export type DocumentStatus = "processing" | "ready" | "failed" | "deleted";

export interface DocumentResponse {
  id: string;
  company_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}
