"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";

import { useConversation, useConversations } from "@/entities/conversation/api/queries";
import { MessageList } from "@/entities/conversation/ui/message-list";
import { streamAgentMessage } from "@/features/send-message/api/stream-message";
import { MessageInput } from "@/features/send-message/ui/message-input";
import { conversationKeys } from "@/entities/conversation/model/query-keys";
import { useChatStore } from "@/shared/store/chat-store";
import { useNotificationStore } from "@/shared/store/notification-store";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/cn";

import { chatReducer, type ChatState } from "../model/chat-reducer";

export function ChatWindow({
  agentId,
  companyId,
}: Readonly<{ agentId: string; companyId?: string | null }>) {
  const { data: session } = useSession();
  const token = session?.accessToken ?? null;

  const queryClient = useQueryClient();
  const { addNotification } = useNotificationStore();

  const conversationId = useChatStore((s) => s.getConversationId(agentId, companyId));
  const setConversationId = useChatStore((s) => s.setConversationId);
  const clearConversationId = useChatStore((s) => s.clearConversationId);

  const conversationListParams = useMemo(
    () => ({
      agent_id: agentId,
      company_id: companyId ?? null,
      limit: 1,
      offset: 0,
    }),
    [agentId, companyId],
  );
  const latestConversationsQuery = useConversations(token, conversationListParams);
  const conversationQuery = useConversation(conversationId ?? "", token);
  const [loadLatestConversation, setLoadLatestConversation] = useState(true);

  const initialState: ChatState = useMemo(
    () => ({
      messages: [],
      streamingContent: "",
      status: "idle",
      error: null,
    }),
    [],
  );
  const [state, dispatch] = useReducer(chatReducer, initialState);

  const historyLoadedForConversation = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    historyLoadedForConversation.current = null;
    setLoadLatestConversation(true);
  }, [agentId, companyId]);

  useEffect(() => {
    if (conversationId) return;
    if (!loadLatestConversation) return;
    if (!latestConversationsQuery.data) return;

    const latestConversationId = latestConversationsQuery.data[0]?.id ?? null;
    if (latestConversationId) {
      setConversationId(agentId, companyId, latestConversationId);
      return;
    }

    clearConversationId(agentId, companyId);
    dispatch({ type: "RESET" });
  }, [
    agentId,
    clearConversationId,
    companyId,
    conversationId,
    loadLatestConversation,
    latestConversationsQuery.data,
    setConversationId,
  ]);

  useEffect(() => {
    if (!conversationId) return;
    if (!conversationQuery.data) return;
    if (historyLoadedForConversation.current === conversationId) return;

    historyLoadedForConversation.current = conversationId;
    dispatch({ type: "LOAD_HISTORY", payload: conversationQuery.data.messages });
  }, [conversationId, conversationQuery.data]);

  useEffect(() => {
    if (!conversationId || !conversationQuery.isError) return;

    clearConversationId(agentId, companyId);
    historyLoadedForConversation.current = null;
    dispatch({ type: "RESET" });
  }, [agentId, clearConversationId, companyId, conversationId, conversationQuery.isError]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [state.messages.length, state.streamingContent]);

  async function sendMessage(message: string) {
    if (!token) {
      addNotification("You must be logged in to chat.", "error");
      return;
    }

    dispatch({ type: "SEND_MESSAGE", payload: message });

    try {
      for await (const event of streamAgentMessage({
        agentId,
        message,
        conversationId,
        token,
      })) {
        if (event.event === "conversation") {
          setConversationId(agentId, companyId, event.data.conversation_id);
          historyLoadedForConversation.current = null;
        }
        if (event.event === "token") {
          dispatch({ type: "STREAM_TOKEN", payload: event.data.content });
        }
        if (event.event === "done") {
          dispatch({ type: "STREAM_COMPLETE" });
          await queryClient.invalidateQueries({
            queryKey: conversationKeys.detail(event.data.conversation_id),
          });
          await queryClient.invalidateQueries({
            queryKey: conversationKeys.list(conversationListParams),
          });
        }
        if (event.event === "error") {
          dispatch({ type: "STREAM_ERROR", payload: event.data.message });
          addNotification(event.data.message, "error");
        }
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Chat streaming failed.";
      dispatch({ type: "STREAM_ERROR", payload: message });
      addNotification(message, "error");
    }
  }

  function startNewConversation() {
    setLoadLatestConversation(false);
    clearConversationId(agentId, companyId);
    historyLoadedForConversation.current = null;
    dispatch({ type: "RESET" });
  }

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col overflow-hidden rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-3 border-b bg-background px-4 py-3">
        <div>
          <h2 className="text-sm font-medium">Chat</h2>
          <p className="text-xs text-muted-foreground">
            Start a new conversation or continue the latest one.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={startNewConversation}
          disabled={state.status === "streaming" || (!conversationId && state.messages.length === 0)}
        >
          New conversation
        </Button>
      </div>

      {state.status === "error" && state.error ? (
        <div className="p-3">
          <Alert variant="destructive">{state.error}</Alert>
        </div>
      ) : null}

      <div className={cn("flex-1 overflow-y-auto p-4", state.status === "streaming" ? "opacity-100" : "")}>
        <MessageList
          messages={state.messages}
          streamingContent={state.streamingContent}
        />
        <div ref={bottomRef} />
      </div>

      <MessageInput disabled={state.status === "streaming"} onSend={sendMessage} />
    </div>
  );
}

