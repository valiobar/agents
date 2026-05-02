import { z } from "zod";

import type { Expense } from "@/entities/expense/model/types";
import { expenseCategorySchema } from "@/features/record-expense/model/schema";
import { ApiError } from "@/shared/api/errors";

export const supportedReceiptTypes = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/webp",
] as const;

export const MAX_RECEIPT_SIZE_BYTES = 10 * 1024 * 1024;

export const sourceDocumentTypeSchema = z.enum(["invoice", "receipt"]);
export const uploadSourceDocumentTypeSchema = z.enum(["auto", "invoice", "receipt"]);

const decimalStringSchema = z.string().regex(/^\d+(?:\.\d{1,4})?$/, "Invalid decimal format");
const optionalStringSchema = z.string().nullable().optional();

export const receiptUploadSchema = z.object({
  file: z
    .instanceof(File)
    .refine((file) => supportedReceiptTypes.includes(file.type as (typeof supportedReceiptTypes)[number]), {
      message: "Upload a PDF or an image (PNG, JPEG, WebP)",
    })
    .refine((file) => file.size <= MAX_RECEIPT_SIZE_BYTES, {
      message: "File must be 10 MB or smaller",
    }),
  source_document_type: uploadSourceDocumentTypeSchema,
});

export const extractedPartnerDraftSchema = z.object({
  name: z.string().min(1).max(200),
  registration_number: optionalStringSchema,
  vat_number: optionalStringSchema,
  city: optionalStringSchema,
  country: z.string().max(120).nullable().optional(),
  address: z.string().max(500).nullable().optional(),
  accountable_person: z.string().max(200).nullable().optional(),
  email: z.string().email().nullable().optional(),
  phone: z.string().max(64).nullable().optional(),
  confidence: z.number().min(0).max(1),
  warnings: z.array(z.string()).default([]),
});

const extractedExpenseItemSchema = z.object({
  description: z.string().min(1).max(500),
  quantity: decimalStringSchema.default("1"),
  unit_price: decimalStringSchema,
  unit_label: z.string().max(32).nullable().optional(),
  sku: z.string().max(120).nullable().optional(),
  barcode: z.string().max(120).nullable().optional(),
  vat_rate: decimalStringSchema.nullable().optional(),
  category: expenseCategorySchema.nullable().optional(),
});

export const expenseDraftSchema = z.object({
  counterparty: z.string().min(1).max(200),
  expense_date: z.string().min(1),
  amount: decimalStringSchema.nullable().optional(),
  currency: z.enum(["BGN", "EUR", "USD"]).default("EUR"),
  category: expenseCategorySchema,
  description: z.string().max(1000).nullable().optional(),
  deductible: z.boolean().default(true),
  deductible_rate: decimalStringSchema.default("1.0"),
  source_document_type: sourceDocumentTypeSchema,
  source_document_id: z.string().min(1),
  source_document_number: z.string().max(120).nullable().optional(),
  vendor_partner: extractedPartnerDraftSchema.nullable().optional(),
  items: z.array(extractedExpenseItemSchema).nullable().optional(),
  confidence: z.number().min(0).max(1),
  warnings: z.array(z.string()).default([]),
});

export const confirmExtractedExpenseInputSchema = expenseDraftSchema
  .extend({
    confirmed: z.literal(true),
  })
  .superRefine((value, context) => {
    if (value.source_document_type !== "invoice") {
      return;
    }

    if (!value.vendor_partner) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["vendor_partner"],
        message: "Invoice confirmation requires reviewed vendor partner details.",
      });
    }
  });

export const expenseDraftConfirmationSchema = expenseDraftSchema.superRefine((value, context) => {
  if (value.source_document_type !== "invoice") {
    return;
  }

  if (!value.vendor_partner) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["vendor_partner"],
      message: "Invoice confirmation requires reviewed vendor partner details.",
    });
  }
});

export const partnerUpsertStatusSchema = z.enum(["matched", "created", "skipped"]);

export interface PartnerUpsertResult {
  status: z.infer<typeof partnerUpsertStatusSchema>;
  partner: {
    id: string;
    user_id: string;
    company_id: string;
    kind: "client" | "supplier" | "both" | "other";
    name: string;
    registration_number: string;
    vat_number: string | null;
    city: string;
    country: string;
    address: string;
    accountable_person: string;
    email: string | null;
    phone: string | null;
    notes: string | null;
    created_at: string;
    updated_at: string;
  } | null;
  warnings: string[];
}

export interface ConfirmExtractedExpenseResponse {
  expense: Expense;
  vendor_partner: PartnerUpsertResult | null;
}

export type ExpenseDraftFormValues = z.infer<typeof expenseDraftSchema>;
export type ConfirmExtractedExpenseInput = z.infer<typeof confirmExtractedExpenseInputSchema>;

export function getReceiptUploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "Your session expired. Sign in again before uploading receipts.";
    }
    if (error.status === 413) {
      return "The selected file is too large. Upload a file up to 10 MB.";
    }
    if (error.status === 415) {
      return "Unsupported file type. Upload a PDF or an image (PNG, JPEG, WebP).";
    }
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Receipt upload failed. Please try again.";
}
