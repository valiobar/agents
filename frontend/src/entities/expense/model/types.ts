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
  items: unknown[] | null;
  created_at: string;
  updated_at: string;
}
