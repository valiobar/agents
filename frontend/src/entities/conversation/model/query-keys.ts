export interface ConversationListParams {
  [key: string]: string | number | boolean | null | undefined;
  agent_id: string;
  company_id?: string | null;
  limit?: number;
  offset?: number;
}

export const conversationKeys = {
  all: ["conversations"] as const,
  list: (params: ConversationListParams) =>
    [...conversationKeys.all, "list", params] as const,
  detail: (conversationId: string) =>
    [...conversationKeys.all, "detail", conversationId] as const,
};

