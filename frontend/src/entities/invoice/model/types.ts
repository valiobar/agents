export type Currency = "BGN" | "EUR" | "USD";

export type InvoiceStatus = "draft" | "sent" | "paid" | "overdue" | "cancelled";
export type PaymentMethod = "bank_transfer" | "cash" | "card" | "other";

export interface InvoicePartySnapshot {
  name: string;
  registration_number: string;
  vat_number: string | null;
  city: string;
  country: string;
  address: string;
  accountable_person: string;
  logo_data_url: string | null;
  email: string | null;
  phone: string | null;
}

export interface InvoiceItem {
  description: string;
  quantity: string;
  unit_label: string;
  unit_price: string;
  vat_rate: string;
  category: string | null;
  subtotal: string;
  vat_amount: string;
  total: string;
}

export interface Invoice {
  id: string;
  user_id: string;
  company_id: string | null;
  partner_id: string | null;
  invoice_number: string;
  counterparty: string | null;
  supplier_snapshot: InvoicePartySnapshot | null;
  recipient_snapshot: InvoicePartySnapshot | null;
  issue_date: string;
  tax_event_date: string | null;
  due_date: string | null;
  place_of_supply: string | null;
  payment_method: PaymentMethod | null;
  bank_name: string | null;
  bank_bic: string | null;
  bank_iban: string | null;
  amount_in_words: string | null;
  currency: Currency;
  items: InvoiceItem[];
  subtotal: string;
  vat_total: string;
  total: string;
  status: InvoiceStatus;
  vat_reason: string | null;
  recipient_name: string | null;
  compiler_name: string | null;
  original_label: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
