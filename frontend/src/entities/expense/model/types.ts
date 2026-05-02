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
  document: {
    id: string;
    company_id: string;
    filename: string;
    content_type: string;
    size_bytes: number;
    status: "processing" | "ready" | "failed";
    chunk_count: number;
    created_at: string;
    updated_at: string;
  };
  draft: ExpenseDraft;
  extracted_text?: string | null;
  provider: string;
  model: string;
  extracted_at: string;
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
