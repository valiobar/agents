import { z } from "zod";

const emptyStringToNull = (value: unknown) => {
  if (typeof value === "string" && value.trim() === "") {
    return null;
  }
  return value;
};

export const recordStockMovementSchema = z.object({
  company_id: z.string().trim().min(1, "Company is required").max(64, "Company ID is too long"),
  item_id: z.string().trim().min(1, "Item is required").max(64, "Item ID is too long"),
  location_id: z.string().trim().min(1, "Location is required").max(64, "Location ID is too long"),
  movement_type: z.enum(["receipt", "issue", "adjustment", "transfer_in", "transfer_out", "return"]),
  quantity_delta: z
    .string()
    .trim()
    .max(32, "Quantity is too long")
    .regex(/^-?\d+(?:\.\d{1,4})?$/, "Invalid quantity"),
  reason: z.preprocess(
    emptyStringToNull,
    z.string().trim().max(500, "Reason must be at most 500 characters").nullable().optional(),
  ),
});

export type RecordStockMovementInput = z.infer<typeof recordStockMovementSchema>;
