import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import { conversationKeys, type ConversationListParams } from "../model/query-keys";
import type { Conversation } from "../model/types";

export function useConversations(
  token?: string | null,
  params?: ConversationListParams,
) {
  return useQuery({
    queryKey: params ? conversationKeys.list(params) : conversationKeys.all,
    enabled: Boolean(token && params?.agent_id),
    queryFn: () => apiClient.get<Conversation[]>("/conversations", { token, params }),
  });
}

export function useConversation(conversationId: string, token?: string | null) {
  return useQuery({
    queryKey: conversationKeys.detail(conversationId),
    enabled: Boolean(token && conversationId),
    queryFn: () => apiClient.get<Conversation>(`/conversations/${conversationId}`, { token }),
  });
}

