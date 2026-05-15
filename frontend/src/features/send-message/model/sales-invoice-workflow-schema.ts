import { z } from "zod";

import {
  invoiceCreateSchema,
  invoicePartyInputSchema,
  type Invoice,
  type InvoiceCreate,
  type InvoicePartyInput,
} from "@/entities/invoice/model/types";
import type { InventorySearchMatch, StockLevel } from "@/entities/inventory/model/types";
import type { Partner } from "@/entities/partner/model/types";

const decimalStringSchema = z.string().regex(/^\d+(?:\.\d{1,4})?$/, "Invalid decimal format");

export function normalizeVatRateInput(value: string | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return trimmed;
  if (parsed > 1) {
    return (parsed / 100).toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  return trimmed;
}

const partnerSchema = z.object({
  id: z.string().min(1),
  user_id: z.string().min(1),
  company_id: z.string().min(1),
  kind: z.enum(["client", "supplier", "both", "other"]),
  name: z.string().min(1),
  registration_number: z.string().min(1),
  vat_number: z.string().nullable(),
  city: z.string().min(1),
  country: z.string().min(1),
  address: z.string().min(1),
  accountable_person: z.string().min(1),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  notes: z.string().nullable(),
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
});

const partnerMatchCandidateSchema = z.object({
  partner: partnerSchema,
  match_type: z.enum(["id", "registration_number_exact", "vat_exact", "name_exact", "name_prefix", "contains"]),
  score: z.number().min(0).max(1),
  match_reasons: z.array(z.string()).default([]),
});

const inventorySearchMatchSchema = z.object({
  item_id: z.string().min(1),
  name: z.string().min(1),
  description: z.string().nullable(),
  sku: z.string().nullable(),
  category: z.string().nullable(),
  unit: z.string().min(1),
  selling_price: decimalStringSchema.nullable(),
  confidence: z.number().min(0).max(1),
  match_reason: z.enum(["sku", "barcode", "alias", "text", "prefix"]),
  available_quantity: decimalStringSchema.nullable(),
});

const stockLevelSchema = z.object({
  item_id: z.string().min(1),
  item_name: z.string().min(1),
  item_sku: z.string().min(1),
  location_id: z.string().min(1),
  location_name: z.string().min(1),
  available_quantity: decimalStringSchema,
  unit: z.string().min(1),
});

export const requestedSalesInvoiceLineSchema = z.object({
  description: z.string().min(1).max(500),
  query: z.string().min(1).max(500),
  quantity: decimalStringSchema,
  unit_label: z.string().max(32).nullable().optional(),
  unit_price: decimalStringSchema.nullable().optional(),
  vat_rate: decimalStringSchema.nullable().optional(),
  category: z.string().max(120).nullable().optional(),
});

export const createSalesInvoiceInventoryPreviewPayloadSchema = z
  .object({
    partner_query: z.string().max(200).nullable().optional(),
    recipient: invoicePartyInputSchema.nullable().optional(),
    issue_date: z.string().min(1).nullable().optional(),
    tax_event_date: z.string().min(1).nullable().optional(),
    due_date: z.string().min(1).nullable().optional(),
    currency: z.enum(["BGN", "EUR", "USD"]).default("EUR"),
    notes: z.string().max(2000).nullable().optional(),
    lines: z.array(requestedSalesInvoiceLineSchema).min(1),
  })
  .superRefine((value, context) => {
    const hasPartnerQuery = typeof value.partner_query === "string" && value.partner_query.trim().length > 0;
    if (hasPartnerQuery || value.recipient) {
      return;
    }

    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["partner_query"],
      message: "Provide partner_query or recipient.",
    });
  });

export const confirmedSalesInvoiceInventoryLineSchema = z.object({
  line_index: z.number().int().nonnegative(),
  description: z.string().min(1).max(500),
  quantity: decimalStringSchema,
  unit_label: z.string().min(1).max(32),
  unit_price: decimalStringSchema,
  vat_rate: decimalStringSchema,
  category: z.string().max(120).nullable().optional(),
  inventory_item_id: z.string().min(1),
  inventory_location_id: z.string().min(1),
  stock_quantity: decimalStringSchema.nullable().optional(),
});

export const confirmSalesInvoiceInventoryPayloadSchema = z.object({
  source_preview: createSalesInvoiceInventoryPreviewPayloadSchema,
  selected_partner_id: z.string().min(1).nullable().optional(),
  recipient: invoicePartyInputSchema.nullable().optional(),
  lines: z.array(confirmedSalesInvoiceInventoryLineSchema).min(1),
});

export const confirmSalesInvoicePayloadSchema = z.object({
  invoice_draft: invoiceCreateSchema,
  confirmed: z.literal(true),
});

export const resolvedSalesInvoiceInventoryLineSchema = z.object({
  line_index: z.number().int().nonnegative(),
  requested: requestedSalesInvoiceLineSchema,
  selected_item_id: z.string().nullable(),
  selected_location_id: z.string().nullable(),
  candidates: z.array(inventorySearchMatchSchema).default([]),
  stock_levels: z.array(stockLevelSchema).default([]),
  available_quantity: decimalStringSchema.nullable(),
  warnings: z.array(z.string()).default([]),
});

const invoiceItemSchema = z.object({
  description: z.string().min(1),
  quantity: decimalStringSchema,
  unit_label: z.string().min(1),
  unit_price: decimalStringSchema,
  vat_rate: decimalStringSchema,
  category: z.string().nullable(),
  subtotal: decimalStringSchema,
  vat_amount: decimalStringSchema,
  total: decimalStringSchema,
});

const invoicePartySnapshotSchema = invoicePartyInputSchema.extend({
  email: z.string().nullable(),
  phone: z.string().nullable(),
});

const invoiceSchema = z.object({
  id: z.string().min(1),
  user_id: z.string().min(1),
  company_id: z.string().nullable(),
  partner_id: z.string().nullable(),
  invoice_number: z.string().min(1),
  counterparty: z.string().nullable(),
  supplier_snapshot: invoicePartySnapshotSchema.nullable(),
  recipient_snapshot: invoicePartySnapshotSchema.nullable(),
  issue_date: z.string().min(1),
  tax_event_date: z.string().nullable(),
  due_date: z.string().nullable(),
  place_of_supply: z.string().nullable(),
  payment_method: z.enum(["bank_transfer", "cash", "card", "other"]).nullable(),
  bank_name: z.string().nullable(),
  bank_bic: z.string().nullable(),
  bank_iban: z.string().nullable(),
  amount_in_words: z.string().nullable(),
  currency: z.enum(["BGN", "EUR", "USD"]),
  items: z.array(invoiceItemSchema),
  subtotal: decimalStringSchema,
  vat_total: decimalStringSchema,
  total: decimalStringSchema,
  status: z.enum(["draft", "sent", "paid", "overdue", "cancelled"]),
  vat_reason: z.string().nullable(),
  recipient_name: z.string().nullable(),
  compiler_name: z.string().nullable(),
  original_label: z.string().nullable(),
  notes: z.string().nullable(),
  created_at: z.string().min(1),
  updated_at: z.string().min(1),
});

export const salesInvoiceWorkflowResponseSchema = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("sales_invoice_inventory_review"),
    company_id: z.string().min(1),
    partner_query: z.string().nullable(),
    recipient: invoicePartyInputSchema.nullable(),
    partner_candidates: z.array(partnerMatchCandidateSchema).default([]),
    lines: z.array(resolvedSalesInvoiceInventoryLineSchema),
    warnings: z.array(z.string()).default([]),
  }),
  z.object({
    type: z.literal("sales_invoice_review"),
    company_id: z.string().min(1),
    invoice_draft: invoiceCreateSchema,
    inventory_warnings: z.array(z.string()).default([]),
    partner_warnings: z.array(z.string()).default([]),
  }),
  z.object({
    type: z.literal("sales_invoice_created"),
    invoice: invoiceSchema,
    warnings: z.array(z.string()).default([]),
  }),
]);

export interface CreateSalesInvoiceInventoryPreviewInput {
  payload: z.infer<typeof createSalesInvoiceInventoryPreviewPayloadSchema>;
}

export interface ConfirmSalesInvoiceInventoryInput {
  payload: z.infer<typeof confirmSalesInvoiceInventoryPayloadSchema>;
}

export interface ConfirmSalesInvoiceInput {
  invoiceDraft: InvoiceCreate;
}

export type RequestedSalesInvoiceLine = z.infer<typeof requestedSalesInvoiceLineSchema>;
export type ConfirmedSalesInvoiceInventoryLine = z.infer<typeof confirmedSalesInvoiceInventoryLineSchema>;
export type ConfirmSalesInvoiceInventoryPayload = z.infer<typeof confirmSalesInvoiceInventoryPayloadSchema>;
export type ConfirmSalesInvoicePayload = z.infer<typeof confirmSalesInvoicePayloadSchema>;
export type ResolvedSalesInvoiceInventoryLine = z.infer<typeof resolvedSalesInvoiceInventoryLineSchema>;
export type SalesInvoiceWorkflowResponse = z.infer<typeof salesInvoiceWorkflowResponseSchema>;
export type SalesInvoiceInventoryReview = Extract<SalesInvoiceWorkflowResponse, { type: "sales_invoice_inventory_review" }>;
export type SalesInvoiceReview = Extract<SalesInvoiceWorkflowResponse, { type: "sales_invoice_review" }>;
export type SalesInvoiceCreatedResponse = Extract<SalesInvoiceWorkflowResponse, { type: "sales_invoice_created" }>;
export type PartnerMatchCandidate = z.infer<typeof partnerMatchCandidateSchema> & { partner: Partner };
export type InventorySearchMatchResult = z.infer<typeof inventorySearchMatchSchema> & InventorySearchMatch;
export type InventoryStockLevel = z.infer<typeof stockLevelSchema> & StockLevel;
export type SalesInvoiceCreatedInvoice = z.infer<typeof invoiceSchema> & Invoice;
export type SalesInvoiceRecipient = InvoicePartyInput;
