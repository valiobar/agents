import { useMutation, useQueryClient } from "@tanstack/react-query";

import { agentKeys } from "@/entities/agent/model/query-keys";
import type { Agent } from "@/entities/agent/model/types";
import { apiClient } from "@/shared/api/client";

import type { UpdateAgentInput } from "../model/schema";

interface UpdateAgentVariables {
  agentId: string;
  input: UpdateAgentInput;
}

export function useUpdateAgent(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ agentId, input }: UpdateAgentVariables) =>
      apiClient.patch<Agent>(`/agents/${agentId}`, input, { token }),
    onSuccess: async (agent) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: agentKeys.all }),
        queryClient.invalidateQueries({ queryKey: agentKeys.detail(agent.id) }),
      ]);
    },
  });
}
