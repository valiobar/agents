import { z } from "zod";

const emptyStringToNull = (value: unknown) => {
  if (typeof value === "string" && value.trim() === "") {
    return null;
  }
  return value;
};

const nullableText = (max: number, message: string) =>
  z.preprocess(emptyStringToNull, z.string().trim().max(max, message).nullable().optional());

const nullableDecimal = (message: string) =>
  z.preprocess(
    emptyStringToNull,
    z
      .string()
      .trim()
      .max(32, message)
      .refine((value) => /^\d+(?:\.\d+)?$/.test(value), message)
      .nullable()
      .optional(),
  );

export const createInventoryItemSchema = z.object({
  company_id: z.string().trim().min(1, "Company is required").max(64, "Company ID is too long"),
  sku: z.string().trim().min(1, "SKU is required").max(64, "SKU is too long"),
  name: z.string().trim().min(1, "Name is required").max(300, "Name is too long"),
  description: nullableText(2000, "Description is too long"),
  category: nullableText(120, "Category is too long"),
  barcode: nullableText(128, "Barcode is too long"),
  aliases: z.preprocess(
    (value) => {
      if (typeof value === "string") {
        return value
          .split(",")
          .map((alias) => alias.trim())
          .filter(Boolean);
      }
      return value;
    },
    z.array(z.string().trim().min(1).max(120, "Alias is too long")).default([]),
  ),
  unit: z.string().trim().min(1, "Unit is required").max(32, "Unit is too long").default("pcs"),
  selling_price: nullableDecimal("Selling price must be a non-negative number"),
  reorder_point: nullableDecimal("Reorder point must be a non-negative number"),
  target_stock_level: nullableDecimal("Target stock level must be a non-negative number"),
  supplier_partner_id: nullableText(64, "Supplier partner ID is too long"),
});

export type CreateInventoryItemInput = z.infer<typeof createInventoryItemSchema>;

export const updateInventoryItemSchema = createInventoryItemSchema.omit({ company_id: true }).partial();

export type UpdateInventoryItemInput = z.infer<typeof updateInventoryItemSchema>;
