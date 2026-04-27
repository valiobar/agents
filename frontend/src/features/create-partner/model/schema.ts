import { z } from "zod";

const optionalString = (max: number) =>
  z
    .string()
    .max(max)
    .transform((value) => value.trim() || null)
    .nullable()
    .optional();

const optionalEmail = z
  .string()
  .transform((value) => value.trim())
  .pipe(z.string().email().or(z.literal("")))
  .transform((value) => value || null)
  .nullable()
  .optional();

export const partnerKindSchema = z.enum(["client", "supplier", "both", "other"]);

export const partnerSchema = z.object({
  company_id: z.string().min(1, "Company is required"),
  kind: partnerKindSchema.default("client"),
  name: z.string().trim().min(1).max(200),
  registration_number: z.string().trim().min(1).max(64),
  vat_number: optionalString(64),
  city: z.string().trim().min(1).max(120),
  country: z.string().trim().min(1).max(120).default("Bulgaria"),
  address: z.string().trim().min(1).max(500),
  accountable_person: z.string().trim().min(1).max(200),
  email: optionalEmail,
  phone: optionalString(64),
  notes: optionalString(1000),
});

export type PartnerInput = z.infer<typeof partnerSchema>;
