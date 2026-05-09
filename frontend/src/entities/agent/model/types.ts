export type AgentType = "accountant" | "inventory" | "router";
export type LLMProvider = "openai" | "anthropic" | "deepseek" | "ollama";

export interface AgentConfig {
  provider: LLMProvider;
  model: string | null;
  temperature: number;
  system_prompt_override: string | null;
}

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  agent_type: AgentType;
  company_id: string | null;
  config: AgentConfig;
  created_at: string;
  updated_at: string;
}

