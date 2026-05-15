export type Currency = "BGN" | "EUR" | "USD";

export type ExpenseCategory =
  | "office"
  | "travel"
  | "meals"
  | "software"
  | "rent"
  | "utilities"
  | "professional_services"
  | "tax"
  | "payroll"
  | "other";

export type ExpenseSourceDocumentType = "invoice" | "receipt";
export type ExpenseDraftRequestSourceDocumentType = "auto" | ExpenseSourceDocumentType;
export type ClassifiedDocumentType =
  | "receipt"
  | "supplier_invoice"
  | "contract"
  | "csv_inventory_import"
  | "json_data_import"
  | "unknown";

export interface DocumentClassification {
  document_type: ClassifiedDocumentType;
  confidence: number;
  warnings: string[];
}

export interface IntakeDocumentResponse {
  id: string;
  company_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: "processing" | "ready" | "failed" | "deleted";
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface ExtractedExpenseItem {
  description: string;
  quantity: string;
  unit_price: string;
  unit_label?: string | null;
  sku?: string | null;
  barcode?: string | null;
  vat_rate?: string | null;
  category?: ExpenseCategory | null;
}

export interface ExtractedPartnerDraft {
  name: string;
  registration_number?: string | null;
  vat_number?: string | null;
  city?: string | null;
  country?: string | null;
  address?: string | null;
  accountable_person?: string | null;
  email?: string | null;
  phone?: string | null;
  confidence: number;
  warnings: string[];
}

export interface ExpenseDraft {
  counterparty: string;
  expense_date: string;
  amount?: string | null;
  currency: Currency;
  category: ExpenseCategory;
  description?: string | null;
  deductible: boolean;
  deductible_rate: string;
  source_document_type: ExpenseSourceDocumentType;
  source_document_id: string;
  source_document_number?: string | null;
  vendor_partner?: ExtractedPartnerDraft | null;
  items?: ExtractedExpenseItem[] | null;
  confidence: number;
  warnings: string[];
}

export interface ExpenseDraftResponse {
  document: IntakeDocumentResponse;
  draft: ExpenseDraft;
  extracted_text?: string | null;
  provider: string;
  model: string;
  extracted_at: string;
}

export interface ReceiptExpenseReviewResponse extends ExpenseDraftResponse {
  type: "receipt_expense_review";
  classification: DocumentClassification;
}

export interface SupplierInvoiceExpenseReviewResponse extends ExpenseDraftResponse {
  type: "supplier_invoice_expense_review";
  classification: DocumentClassification;
}

export interface SupplierInvoiceInventoryReviewResponse extends ExpenseDraftResponse {
  type: "supplier_invoice_inventory_review";
  classification: DocumentClassification;
  inventory_import_preview: import("@/entities/inventory/model/types").InventoryImportPreview;
}

export interface UnknownDocumentReviewResponse {
  type: "unknown_document_review";
  classification: DocumentClassification;
  document: IntakeDocumentResponse | null;
  extracted_text: string | null;
  warnings: string[];
}

export type DocumentIntakeResponse =
  | ReceiptExpenseReviewResponse
  | SupplierInvoiceExpenseReviewResponse
  | SupplierInvoiceInventoryReviewResponse
  | UnknownDocumentReviewResponse;

export interface ConfirmInventoryImportForExpenseResponse {
  type: "supplier_invoice_expense_review";
  inventory_import_result: import("@/entities/inventory/model/types").InventoryImportResult;
  inventory_import_preview: import("@/entities/inventory/model/types").InventoryImportPreview;
  draft: ExpenseDraft;
}

export interface Expense {
  id: string;
  user_id: string;
  counterparty: string;
  expense_date: string;
  amount: string;
  currency: Currency;
  category: ExpenseCategory;
  description: string | null;
  deductible: boolean;
  deductible_rate: string;
  deductible_amount: string;
  source_document_type: ExpenseSourceDocumentType | null;
  source_document_id: string | null;
  source_document_number: string | null;
  items: unknown[] | null;
  created_at: string;
  updated_at: string;
}

export interface ExpenseListResponse {
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  truncated: boolean;
  next_offset: number | null;
  items: Expense[];
}
