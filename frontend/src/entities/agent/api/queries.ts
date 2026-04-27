import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import { agentKeys, type AgentListParams } from "../model/query-keys";
import type { Agent } from "../model/types";

const DEFAULT_AGENT_LIST_PARAMS: AgentListParams = { limit: 50, offset: 0 };

export function useAgents(
  token?: string | null,
  params: AgentListParams = DEFAULT_AGENT_LIST_PARAMS,
) {
  return useQuery({
    queryKey: agentKeys.list(params),
    enabled: Boolean(token),
    queryFn: () => apiClient.get<Agent[]>("/agents", { token, params }),
  });
}

export function useAgent(agentId: string, token?: string | null) {
  return useQuery({
    queryKey: agentKeys.detail(agentId),
    enabled: Boolean(token && agentId),
    queryFn: () => apiClient.get<Agent>(`/agents/${agentId}`, { token }),
  });
}

