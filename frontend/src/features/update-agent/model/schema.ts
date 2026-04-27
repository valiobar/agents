import { z } from "zod";

function emptyStringToNull(value: unknown) {
  if (typeof value === "string" && value.trim() === "") return null;
  return value;
}

export const updateAgentSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  description: z.preprocess(
    emptyStringToNull,
    z.string().max(1000, "Description is too long").nullable().optional(),
  ),
  company_id: z.preprocess(
    emptyStringToNull,
    z.string().max(64, "Company ID is too long").nullable().optional(),
  ),
  config: z.object({
    provider: z.enum(["openai", "anthropic", "deepseek", "ollama"]),
    model: z.preprocess(emptyStringToNull, z.string().nullable().optional()),
    temperature: z.coerce.number().min(0).max(2),
    system_prompt_override: z.preprocess(
      emptyStringToNull,
      z.string().max(4000, "System prompt is too long").nullable().optional(),
    ),
  }),
});

export type UpdateAgentInput = z.infer<typeof updateAgentSchema>;
