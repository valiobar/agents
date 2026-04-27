export interface AgentListParams {
  [key: string]: string | number | boolean | null | undefined;
  company_id?: string;
  limit?: number;
  offset?: number;
}

export const agentKeys = {
  all: ["agents"] as const,
  list: (params: AgentListParams = {}) => [...agentKeys.all, "list", params] as const,
  detail: (agentId: string) => [...agentKeys.all, "detail", agentId] as const,
};

