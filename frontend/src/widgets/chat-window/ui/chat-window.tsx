"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";

import { useConversation, useConversations } from "@/entities/conversation/api/queries";
import { MessageList } from "@/entities/conversation/ui/message-list";
import { expenseKeys } from "@/entities/expense/model/query-keys";
import { partnerKeys } from "@/entities/partner/model/query-keys";
import { streamAgentMessage } from "@/features/send-message/api/stream-message";
import { confirmExtractedExpense, createExpenseDraft } from "@/features/send-message/api/receipt-expense";
import { ExpenseDraftConfirmation } from "@/features/send-message/ui/expense-draft-confirmation";
import { MessageInput } from "@/features/send-message/ui/message-input";
import { conversationKeys } from "@/entities/conversation/model/query-keys";
import { documentKeys } from "@/features/upload-document/api/mutations";
import { useChatStore } from "@/shared/store/chat-store";
import { useNotificationStore } from "@/shared/store/notification-store";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/cn";
import { buildExpenseConfirmationMessage } from "@/features/send-message/model/expense-confirmation-message";
import { receiptUploadSchema, getReceiptUploadErrorMessage, type ExpenseDraftFormValues } from "@/features/send-message/model/receipt-expense-schema";
import { Spinner } from "@/shared/ui/spinner";

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
      expenseDraftStatus: "idle",
      expenseDraft: null,
      expenseDraftError: null,
    }),
    [],
  );
  const [state, dispatch] = useReducer(chatReducer, initialState);

  const historyLoadedForConversation = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const isExtractingExpense = state.expenseDraftStatus === "loading";
  const isConfirmingExpense = state.expenseDraftStatus === "confirming";
  const isExpenseConfirmed = state.expenseDraftStatus === "confirmed";
  const hasActiveExpenseDraft =
    state.expenseDraftStatus === "loading" ||
    state.expenseDraftStatus === "ready" ||
    state.expenseDraftStatus === "confirming";

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
  }, [state.messages.length, state.streamingContent, state.expenseDraftStatus]);

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

  async function handleReceiptSelected(file: File) {
    if (!token) {
      addNotification("You must be logged in to upload receipts.", "error");
      return;
    }
    if (!companyId) {
      addNotification("Assign this agent to a company before uploading receipts.", "error");
      return;
    }
    if (state.status === "streaming") {
      addNotification("Please wait for the current response to finish before uploading a receipt.", "info");
      return;
    }

    const validation = receiptUploadSchema.safeParse({ file, source_document_type: "auto" });
    if (!validation.success) {
      addNotification(validation.error.issues[0]?.message ?? "Invalid receipt file.", "error");
      return;
    }

    dispatch({ type: "EXPENSE_DRAFT_LOADING" });
    try {
      const response = await createExpenseDraft({
        agentId,
        file,
        sourceDocumentType: "auto",
        token,
      });
      dispatch({ type: "EXPENSE_DRAFT_READY", payload: response.draft });
    } catch (error) {
      dispatch({ type: "EXPENSE_DRAFT_ERROR", payload: getReceiptUploadErrorMessage(error) });
      addNotification(getReceiptUploadErrorMessage(error), "error");
    }
  }

  async function handleDraftConfirm(values: ExpenseDraftFormValues) {
    if (!token) {
      addNotification("You must be logged in to confirm expenses.", "error");
      return;
    }

    dispatch({ type: "EXPENSE_CONFIRMING" });

    try {
      const response = await confirmExtractedExpense({
        agentId,
        token,
        draft: values,
      });

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: expenseKeys.all }),
        queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
        queryClient.invalidateQueries({ queryKey: documentKeys.all }),
      ]);

      dispatch({
        type: "EXPENSE_CONFIRMATION_SUCCEEDED",
        payload: {
          content: buildExpenseConfirmationMessage(response),
        },
      });

      const partnerMessage =
        response.vendor_partner?.status === "created"
          ? " Supplier partner created."
          : response.vendor_partner?.status === "matched"
            ? " Supplier partner matched."
            : "";
      addNotification(`Expense recorded: ${response.expense.counterparty}.${partnerMessage}`, "success");
    } catch (error) {
      dispatch({ type: "EXPENSE_DRAFT_READY", payload: values });
      throw error;
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
        {isExtractingExpense ? (
          <output
            className="mt-3 flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground"
          >
            <Spinner />
            <span>Reading document and extracting expense details...</span>
          </output>
        ) : null}
        {(state.expenseDraftStatus === "ready" ||
          state.expenseDraftStatus === "confirming" ||
          state.expenseDraftStatus === "confirmed") &&
        state.expenseDraft ? (
          <ExpenseDraftConfirmation
            draft={state.expenseDraft}
            disabled={state.status === "streaming"}
            confirming={isConfirmingExpense}
            confirmed={isExpenseConfirmed}
            onCancel={() => dispatch({ type: "EXPENSE_DRAFT_CLEAR" })}
            onConfirm={handleDraftConfirm}
          />
        ) : null}
        <div ref={bottomRef} />
      </div>

      {state.expenseDraftStatus === "error" && state.expenseDraftError ? (
        <div className="px-4 pt-3">
          <Alert variant="destructive">{state.expenseDraftError}</Alert>
        </div>
      ) : null}

      <MessageInput
        disabled={state.status === "streaming" || isConfirmingExpense}
        receiptUploadDisabled={!companyId || state.status === "streaming" || hasActiveExpenseDraft}
        receiptUploadLoading={isExtractingExpense}
        onReceiptSelected={handleReceiptSelected}
        onSend={sendMessage}
      />
    </div>
  );
}

