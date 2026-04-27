import { z } from "zod";

export const MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024;

export const supportedDocumentTypes = [
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
  "application/x-markdown",
] as const;

const supportedDocumentExtensions = [".pdf", ".txt", ".md", ".markdown"] as const;

function hasSupportedDocumentType(file: File) {
  const lowerName = file.name.toLowerCase();
  return (
    supportedDocumentTypes.includes(
      file.type as (typeof supportedDocumentTypes)[number],
    ) || supportedDocumentExtensions.some((extension) => lowerName.endsWith(extension))
  );
}

export const uploadDocumentSchema = z.object({
  company_id: z.string().min(1, "Company is required"),
  file: z
    .instanceof(File)
    .refine(hasSupportedDocumentType, {
      message: "Upload a PDF, text, or Markdown file",
    })
    .refine((file) => file.size <= MAX_DOCUMENT_SIZE_BYTES, {
      message: "File must be 10 MB or smaller",
    }),
});

export type UploadDocumentInput = z.infer<typeof uploadDocumentSchema>;
