import { z } from "zod";

export const expenseCategorySchema = z.enum([
  "office",
  "travel",
  "meals",
  "software",
  "rent",
  "utilities",
  "professional_services",
  "tax",
  "payroll",
  "other",
]);

const moneyString = z.string().regex(/^\d+(?:\.\d{1,4})?$/, "Invalid amount format");
const rateString = z
  .string()
  .regex(/^0(?:\.\d+)?$|^1(?:\.0+)?$/, "Rate must be between 0 and 1");

export const recordExpenseSchema = z.object({
  counterparty: z.string().min(1).max(200),
  expense_date: z.string().min(1),
  amount: moneyString,
  currency: z.enum(["BGN", "EUR", "USD"]).default("EUR"),
  category: expenseCategorySchema,
  description: z.string().max(1000).optional().nullable(),
  deductible: z.boolean().default(true),
  deductible_rate: rateString.default("1.0"),
  source_document_type: z.enum(["invoice", "receipt"]).optional().nullable(),
  source_document_id: z.string().optional().nullable(),
});

export type RecordExpenseInput = z.infer<typeof recordExpenseSchema>;

