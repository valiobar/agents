import { create } from "zustand";
import { persist } from "zustand/middleware";

function conversationScopeKey(agentId: string, companyId?: string | null) {
  return `${agentId}:${companyId ?? "unassigned"}`;
}

interface ChatStoreState {
  conversationByScope: Record<string, string | null | undefined>;
  getConversationId: (agentId: string, companyId?: string | null) => string | null;
  setConversationId: (agentId: string, companyId: string | null | undefined, conversationId: string | null) => void;
  clearConversationId: (agentId: string, companyId?: string | null) => void;
}

export const useChatStore = create<ChatStoreState>()(
  persist(
    (set, get) => ({
      conversationByScope: {},
      getConversationId: (agentId, companyId) =>
        get().conversationByScope[conversationScopeKey(agentId, companyId)] ?? null,
      setConversationId: (agentId, companyId, conversationId) =>
        set((state) => ({
          conversationByScope: {
            ...state.conversationByScope,
            [conversationScopeKey(agentId, companyId)]: conversationId,
          },
        })),
      clearConversationId: (agentId, companyId) =>
        set((state) => ({
          conversationByScope: {
            ...state.conversationByScope,
            [conversationScopeKey(agentId, companyId)]: null,
          },
        })),
    }),
    { name: "chat-state" },
  ),
);

