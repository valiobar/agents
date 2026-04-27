import { z } from "zod";

function emptyStringToNull(value: unknown) {
  if (typeof value === "string" && value.trim() === "") return null;
  return value;
}

export const createAgentSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  description: z.preprocess(
    emptyStringToNull,
    z.string().max(1000, "Description is too long").nullable().optional(),
  ),
  agent_type: z.literal("accountant").default("accountant"),
  company_id: z.preprocess(
    emptyStringToNull,
    z.string().max(64, "Company ID is too long").nullable().optional(),
  ),
  config: z.object({
    provider: z.enum(["openai", "anthropic", "deepseek", "ollama"]).default("openai"),
    model: z.preprocess(emptyStringToNull, z.string().nullable().optional()),
    temperature: z.coerce.number().min(0).max(2).default(0.2),
    system_prompt_override: z.preprocess(
      emptyStringToNull,
      z.string().max(4000, "System prompt is too long").nullable().optional(),
    ),
  }),
});

export type CreateAgentInput = z.infer<typeof createAgentSchema>;

