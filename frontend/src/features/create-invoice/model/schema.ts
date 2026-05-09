import { z } from "zod";

const decimalString = (opts?: { maxDecimals?: number }) => {
  const maxDecimals = opts?.maxDecimals ?? 4;
  const re = new RegExp(String.raw`^\d+(?:\.\d{1,${maxDecimals}})?$`);
  return z.string().regex(re, "Invalid number format");
};

const vatRateString = z
  .string()
  .regex(/^0(?:\.\d+)?$|^1(?:\.0+)?$/, "VAT rate must be between 0 and 1");

const emptyStringToNull = (value: unknown) => {
  if (typeof value === "string" && value.trim() === "") return null;
  return value;
};

const nullableText = (max: number, message: string) =>
  z.preprocess(emptyStringToNull, z.string().max(max, message).nullable().optional());

export const invoicePartyInputSchema = z.object({
  name: z.string().min(1, "Recipient name is required").max(200),
  registration_number: z.string().min(1, "Registration number is required").max(64),
  vat_number: nullableText(64, "VAT number is too long"),
  city: z.string().min(1, "City is required").max(120),
  country: z.string().min(1, "Country is required").max(120).default("Bulgaria"),
  address: z.string().min(1, "Address is required").max(500),
  accountable_person: z.string().min(1, "Accountable person is required").max(200),
  logo_data_url: z.string().nullable().optional(),
});

export const invoiceItemInputSchema = z.object({
  description: z.string().min(1).max(500),
  quantity: decimalString({ maxDecimals: 4 }),
  unit_label: z.string().min(1, "Unit is required").max(32).default("бр."),
  unit_price: decimalString({ maxDecimals: 4 }),
  vat_rate: vatRateString.default("0.20"),
  category: nullableText(120, "Category is too long"),
  inventory_item_id: z.preprocess(emptyStringToNull, z.string().max(64).nullable().optional()),
  inventory_location_id: z.preprocess(emptyStringToNull, z.string().max(64).nullable().optional()),
  stock_quantity: z.preprocess(emptyStringToNull, decimalString({ maxDecimals: 4 }).nullable().optional()),
});

export const createInvoiceSchema = z
  .object({
    company_id: z.string().min(1, "Company is required"),
    partner_id: z.preprocess(emptyStringToNull, z.string().max(64).nullable().optional()),
    recipient: invoicePartyInputSchema.nullable().optional(),
    issue_date: z.string().min(1),
    tax_event_date: z.string().min(1),
    due_date: z.string().optional().nullable(),
    place_of_supply: z.string().min(1).max(120).default("Bulgaria"),
    payment_method: z.enum(["bank_transfer", "cash", "card", "other"]).default("bank_transfer"),
    bank_name: nullableText(120, "Bank name is too long"),
    bank_bic: nullableText(32, "BIC is too long"),
    bank_iban: nullableText(64, "IBAN is too long"),
    vat_reason: nullableText(500, "VAT reason is too long"),
    recipient_name: nullableText(200, "Recipient name is too long"),
    compiler_name: nullableText(200, "Compiler name is too long"),
    original_label: z.string().min(1).max(64).default("ОРИГИНАЛ"),
    currency: z.enum(["BGN", "EUR", "USD"]).default("EUR"),
    items: z.array(invoiceItemInputSchema).min(1),
    status: z.enum(["draft", "sent", "paid", "overdue", "cancelled"]).default("sent"),
    notes: nullableText(2000, "Notes are too long"),
  })
  .refine((value) => value.partner_id || value.recipient, {
    path: ["partner_id"],
    message: "Select a partner or enter recipient details",
  })
  .refine((value) => !value.due_date || value.due_date >= value.issue_date, {
    path: ["due_date"],
    message: "Due date cannot be before issue date",
  })
  .refine((value) => value.tax_event_date >= value.issue_date, {
    path: ["tax_event_date"],
    message: "Tax event date cannot be before issue date",
  });

export type CreateInvoiceInput = z.infer<typeof createInvoiceSchema>;

