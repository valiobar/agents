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

export const ALLOWED_LOGO_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"] as const;
export const MAX_LOGO_BYTES = 256 * 1024;

export async function fileToLogoDataUrl(file: File): Promise<string> {
  if (!ALLOWED_LOGO_TYPES.includes(file.type as (typeof ALLOWED_LOGO_TYPES)[number])) {
    throw new Error("Unsupported logo type. Use PNG, JPEG, WebP, or GIF.");
  }

  if (file.size > MAX_LOGO_BYTES) {
    throw new Error("Logo must be 256 KB or smaller.");
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Unable to read logo file."));
    reader.readAsDataURL(file);
  });
}

export const companySchema = z.object({
  name: z.string().trim().min(1).max(200),
  registration_number: z.string().trim().min(1).max(64),
  vat_number: optionalString(64),
  city: z.string().trim().min(1).max(120),
  country: z.string().trim().min(1).max(120).default("Bulgaria"),
  address: z.string().trim().min(1).max(500),
  accountable_person: z.string().trim().min(1).max(200),
  email: optionalEmail,
  phone: optionalString(64),
  logo_data_url: z.string().nullable().optional(),
  is_default: z.boolean().default(false),
});

export type CompanyInput = z.infer<typeof companySchema>;
