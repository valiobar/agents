import { z } from "zod";

import { invoicePartyInputSchema } from "@/entities/invoice/model/types";

import {
  createSalesInvoiceInventoryPreviewPayloadSchema,
  normalizeVatRateInput,
  requestedSalesInvoiceLineSchema,
} from "./sales-invoice-workflow-schema";

const salesInvoiceWorkflowSuggestionLineSchema = requestedSalesInvoiceLineSchema
  .partial()
  .extend({
    description: z.string().max(500).optional(),
    query: z.string().max(500).optional(),
    quantity: z.string().optional(),
  });

const salesInvoiceWorkflowPrefillSchema = z.object({
  partner_query: z.string().max(200).nullable().optional(),
  recipient: invoicePartyInputSchema.nullable().optional(),
  currency: z.enum(["BGN", "EUR", "USD"]).nullable().optional(),
  lines: z.array(salesInvoiceWorkflowSuggestionLineSchema).default([]),
});

export const salesInvoiceWorkflowSuggestionSchema = z.object({
  workflow: z.literal("sales_invoice_inventory"),
  confidence: z.number().min(0).max(1),
  reason: z.string().min(1),
  prefill: salesInvoiceWorkflowPrefillSchema,
});

export const workflowSuggestionSchema = z.discriminatedUnion("workflow", [
  salesInvoiceWorkflowSuggestionSchema,
]);

const workflowSuggestionEnvelopeSchema = z.object({
  workflow: z.string().min(1),
  confidence: z.number().min(0).max(1),
  reason: z.string().min(1),
  prefill: z.unknown().optional(),
});

export function parseWorkflowSuggestion(raw: unknown): WorkflowSuggestion | null {
  const envelope = workflowSuggestionEnvelopeSchema.safeParse(raw);
  if (!envelope.success) {
    return null;
  }

  if (envelope.data.workflow !== "sales_invoice_inventory") {
    return null;
  }

  const parsed = workflowSuggestionSchema.safeParse(raw);
  return parsed.success ? parsed.data : null;
}

export function toSalesInvoicePreviewPayload(
  suggestion: SalesInvoiceWorkflowSuggestion,
): z.infer<typeof createSalesInvoiceInventoryPreviewPayloadSchema> | null {
  const parsedLines = suggestion.prefill.lines
    .map((line) => {
      const description = line.description?.trim() ?? "";
      const query = line.query?.trim() ?? "";
      const quantity = line.quantity?.trim() ?? "";
      if (!description || !query || !quantity) {
        return null;
      }
      return {
        description,
        query,
        quantity,
        unit_label: line.unit_label ?? "pcs",
        unit_price: line.unit_price ?? null,
        vat_rate: normalizeVatRateInput(line.vat_rate) ?? "0.20",
        category: line.category ?? null,
      };
    })
    .filter((line): line is NonNullable<typeof line> => line !== null);

  const payloadCandidate = {
    partner_query: suggestion.prefill.partner_query ?? null,
    recipient: suggestion.prefill.recipient ?? null,
    currency: suggestion.prefill.currency ?? "EUR",
    issue_date: null,
    tax_event_date: null,
    due_date: null,
    notes: null,
    lines: parsedLines,
  };
  const payload = createSalesInvoiceInventoryPreviewPayloadSchema.safeParse(payloadCandidate);
  return payload.success ? payload.data : null;
}

export function toSalesInvoiceRequestInitialValues(
  suggestion: SalesInvoiceWorkflowSuggestion,
): z.infer<typeof createSalesInvoiceInventoryPreviewPayloadSchema> {
  const lines =
    suggestion.prefill.lines.length > 0
      ? suggestion.prefill.lines.map((line) => ({
          description: line.description ?? "",
          query: line.query ?? "",
          quantity: line.quantity ?? "",
          unit_label: line.unit_label ?? "pcs",
          unit_price: line.unit_price ?? null,
          vat_rate: normalizeVatRateInput(line.vat_rate) ?? "0.20",
          category: line.category ?? null,
        }))
      : [{ description: "", query: "", quantity: "1", unit_label: "pcs", unit_price: null, vat_rate: "0.20", category: null }];

  return {
    partner_query: suggestion.prefill.partner_query ?? null,
    recipient: suggestion.prefill.recipient ?? null,
    currency: suggestion.prefill.currency ?? "EUR",
    issue_date: null,
    tax_event_date: null,
    due_date: null,
    notes: null,
    lines,
  };
}

export type SalesInvoiceWorkflowSuggestion = z.infer<typeof salesInvoiceWorkflowSuggestionSchema>;
export type WorkflowSuggestion = z.infer<typeof workflowSuggestionSchema>;
