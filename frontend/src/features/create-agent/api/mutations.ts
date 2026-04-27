import { useMutation, useQueryClient } from "@tanstack/react-query";

import { agentKeys } from "@/entities/agent/model/query-keys";
import type { Agent } from "@/entities/agent/model/types";
import { apiClient } from "@/shared/api/client";

import type { CreateAgentInput } from "../model/schema";

export function useCreateAgent(token?: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: CreateAgentInput) => apiClient.post<Agent>("/agents", input, { token }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: agentKeys.all });
    },
  });
}

