import { z } from "zod";

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

export interface InvoicePartyInput {
  name: string;
  registration_number: string;
  vat_number: string | null;
  city: string;
  country: string;
  address: string;
  accountable_person: string;
  logo_data_url: string | null;
}

export interface InvoiceItemCreate {
  description: string;
  quantity: string;
  unit_label: string;
  unit_price: string;
  vat_rate: string;
  category: string | null;
  inventory_item_id: string | null;
  inventory_location_id: string | null;
  stock_quantity: string | null;
}

export interface InvoiceCreate {
  company_id: string;
  partner_id: string | null;
  recipient: InvoicePartyInput | null;
  counterparty: string | null;
  issue_date: string;
  tax_event_date: string;
  due_date: string | null;
  currency: Currency;
  items: InvoiceItemCreate[];
  status: InvoiceStatus;
  notes: string | null;
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

export interface InvoiceListResponse {
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  truncated: boolean;
  next_offset: number | null;
  items: Invoice[];
}

const decimalStringSchema = z.string().regex(/^\d+(?:\.\d{1,4})?$/, "Invalid decimal format");

export const invoicePartyInputSchema = z.object({
  name: z.string().min(1).max(200),
  registration_number: z.string().min(1).max(64),
  vat_number: z.string().max(64).nullable(),
  city: z.string().min(1).max(120),
  country: z.string().min(1).max(120),
  address: z.string().min(1).max(500),
  accountable_person: z.string().min(1).max(200),
  logo_data_url: z.string().nullable(),
});

export const invoiceItemCreateSchema = z.object({
  description: z.string().min(1).max(500),
  quantity: decimalStringSchema,
  unit_label: z.string().min(1).max(32),
  unit_price: decimalStringSchema,
  vat_rate: decimalStringSchema,
  category: z.string().max(120).nullable(),
  inventory_item_id: z.string().max(64).nullable(),
  inventory_location_id: z.string().max(64).nullable(),
  stock_quantity: decimalStringSchema.nullable(),
});

export const invoiceCreateSchema = z.object({
  company_id: z.string().min(1),
  partner_id: z.string().max(64).nullable(),
  recipient: invoicePartyInputSchema.nullable(),
  counterparty: z.string().max(200).nullable(),
  issue_date: z.string().min(1),
  tax_event_date: z.string().min(1),
  due_date: z.string().min(1).nullable(),
  currency: z.enum(["BGN", "EUR", "USD"]),
  items: z.array(invoiceItemCreateSchema).min(1),
  status: z.enum(["draft", "sent", "paid", "overdue", "cancelled"]),
  notes: z.string().max(2000).nullable(),
});
