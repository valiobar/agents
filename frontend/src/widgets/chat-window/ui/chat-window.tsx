"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { getSession, signOut, useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";

import { useConversation, useConversations } from "@/entities/conversation/api/queries";
import { getConversationDisplayTitle } from "@/entities/conversation/model/display-title";
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
import { routes } from "@/shared/config/routes";
import { buildExpenseConfirmationMessage } from "@/features/send-message/model/expense-confirmation-message";
import { receiptUploadSchema, getReceiptUploadErrorMessage, type ExpenseDraftFormValues } from "@/features/send-message/model/receipt-expense-schema";
import { Spinner } from "@/shared/ui/spinner";
import type { RecordStockMovementInput } from "@/features/record-stock-movement/model/schema";
import { StockMovementDraftConfirmation } from "@/features/record-stock-movement/ui/stock-movement-draft-confirmation";
import type { StockMovement } from "@/entities/inventory/model/types";

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
      limit: 20,
      offset: 0,
    }),
    [agentId, companyId],
  );
  const conversationsQuery = useConversations(token, conversationListParams);
  const conversationQuery = useConversation(conversationId ?? "", token);

  const initialState: ChatState = useMemo(
    () => ({
      messages: [],
      streamingContent: "",
      status: "idle",
      error: null,
      expenseDraftStatus: "idle",
      expenseDraft: null,
      expenseDraftError: null,
      toolTraces: [],
    }),
    [],
  );
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const [movementDraft, setMovementDraft] = useState<RecordStockMovementInput | null>(null);
  const isDevelopment = process.env.NODE_ENV === "development";
  const historyLoadedForConversation = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const conversationsMenuRef = useRef<HTMLDetailsElement | null>(null);

  const isExtractingExpense = state.expenseDraftStatus === "loading";
  const isConfirmingExpense = state.expenseDraftStatus === "confirming";
  const isExpenseConfirmed = state.expenseDraftStatus === "confirmed";
  const isAgentThinking =
    state.status === "streaming" && state.streamingContent.length === 0;
  const hasActiveExpenseDraft =
    state.expenseDraftStatus === "loading" ||
    state.expenseDraftStatus === "ready" ||
    state.expenseDraftStatus === "confirming";
  const latestMessage = state.messages.at(-1);
  const latestMessageScrollKey = latestMessage
    ? [
        state.messages.length,
        latestMessage.role,
        latestMessage.content,
        latestMessage.created_at ?? "",
      ].join(":")
    : "";

  useEffect(() => {
    clearConversationId(agentId, companyId);
    historyLoadedForConversation.current = null;
    dispatch({ type: "RESET" });
  }, [agentId, clearConversationId, companyId]);

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
    if (!latestMessageScrollKey) return;

    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [latestMessageScrollKey]);

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      const menu = conversationsMenuRef.current;
      const target = event.target;
      if (!menu || !menu.open || !(target instanceof Node)) return;
      if (menu.contains(target)) return;
      menu.open = false;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (conversationsMenuRef.current?.open) {
        conversationsMenuRef.current.open = false;
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  function isUnauthorizedError(error: unknown) {
    if (!(error instanceof Error)) return false;
    return /\b401\b/.test(error.message) || /unauthorized/i.test(error.message);
  }

  async function resolveActiveToken() {
    const latestSession = await getSession();
    if (latestSession?.error === "RefreshAccessTokenError") {
      void signOut({ callbackUrl: routes.login });
      return null;
    }
    return latestSession?.accessToken ?? token;
  }

  async function sendMessage(message: string) {
    const activeToken = await resolveActiveToken();
    if (!activeToken) {
      addNotification("You must be logged in to chat.", "error");
      void signOut({ callbackUrl: routes.login });
      return;
    }

    dispatch({ type: "SEND_MESSAGE", payload: message });
    setMovementDraft(null);

    try {
      for await (const event of streamAgentMessage({
        agentId,
        message,
        conversationId,
        token: activeToken,
      })) {
        if (event.event === "route") {
          continue;
        }
        if (event.event === "conversation") {
          setConversationId(agentId, companyId, event.data.conversation_id);
          historyLoadedForConversation.current = null;
        }
        if (event.event === "token") {
          console.log("STREAM_TOKEN", event.data.content);
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
        if (event.event === "inventory_movement_draft") {
          setMovementDraft(event.data.movement_draft);
        }
        if (event.event === "tool_trace") {
          dispatch({ type: "TOOL_TRACE", payload: event.data });
          if (isDevelopment) {
            console.debug("[tool_trace]", event.data);
          }
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
      if (isUnauthorizedError(err)) {
        void signOut({ callbackUrl: routes.login });
      }
    }
  }

  function buildMovementRecordedMessage(values: RecordStockMovementInput): string {
    const reasonText = values.reason?.trim() ? `\nReason: ${values.reason.trim()}` : "";
    return [
      "Stock movement recorded:",
      `- Movement type: ${values.movement_type}`,
      `- Quantity: ${values.quantity_delta}`,
      `- Item ID: ${values.item_id}`,
      `- Location ID: ${values.location_id}`,
      reasonText,
    ]
      .filter(Boolean)
      .join("\n");
  }

  function handleMovementDraftSuccess(_movement: StockMovement, submittedValues: RecordStockMovementInput) {
    dispatch({
      type: "APPEND_ASSISTANT_MESSAGE",
      payload: {
        content: buildMovementRecordedMessage(submittedValues),
        metadata: { kind: "inventory_movement_confirmation" },
      },
    });
    setMovementDraft(null);
    addNotification("Stock movement recorded.", "success");
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

      let partnerMessage = "";
      if (response.vendor_partner?.status === "created") {
        partnerMessage = " Supplier partner created.";
      } else if (response.vendor_partner?.status === "matched") {
        partnerMessage = " Supplier partner matched.";
      }
      addNotification(`Expense recorded: ${response.expense.counterparty}.${partnerMessage}`, "success");
    } catch (error) {
      dispatch({ type: "EXPENSE_DRAFT_READY", payload: values });
      throw error;
    }
  }

  function startNewConversation() {
    if (conversationsMenuRef.current?.open) {
      conversationsMenuRef.current.open = false;
    }
    clearConversationId(agentId, companyId);
    historyLoadedForConversation.current = null;
    dispatch({ type: "RESET" });
  }

  function openConversation(nextConversationId: string) {
    if (state.status === "streaming") return;
    if (conversationId === nextConversationId) return;

    if (conversationsMenuRef.current?.open) {
      conversationsMenuRef.current.open = false;
    }
    setConversationId(agentId, companyId, nextConversationId);
    historyLoadedForConversation.current = null;
    dispatch({ type: "RESET" });
  }

  return (
    <div className="flex h-[calc(100vh-10rem)] flex-col overflow-hidden rounded-lg border bg-card">
      <div className="flex items-center justify-between gap-3 border-b bg-background px-4 py-3">
        <div>
          <h2 className="text-sm font-medium">Chat</h2>
          <p className="text-xs text-muted-foreground">
            Start a new conversation or reopen previous ones.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <details ref={conversationsMenuRef} className="relative">
            <summary
              className={cn(
                "list-none cursor-pointer rounded-md border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              )}
            >
              Conversations
            </summary>
            <div className="absolute right-0 z-10 mt-2 w-72 rounded-md border border-border bg-background p-2 text-foreground shadow-md">
              {conversationsQuery.data?.length ? (
                <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
                  {conversationsQuery.data.map((conversation) => (
                    <button
                      key={conversation.id}
                      type="button"
                      disabled={state.status === "streaming" || conversation.id === conversationId}
                      className={cn(
                        "w-full rounded-md bg-background px-2 py-1.5 text-left text-sm transition-colors",
                        conversation.id === conversationId
                          ? "cursor-default bg-muted text-muted-foreground"
                          : "hover:bg-accent hover:text-accent-foreground",
                        state.status === "streaming" && "opacity-70",
                      )}
                      onClick={() => openConversation(conversation.id)}
                    >
                      {getConversationDisplayTitle(conversation)}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="px-2 py-1 text-sm text-muted-foreground">
                  No previous conversations.
                </p>
              )}
            </div>
          </details>

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
      </div>

      {state.status === "error" && state.error ? (
        <div className="p-3">
          <Alert variant="destructive">{state.error}</Alert>
        </div>
      ) : null}

      {isDevelopment && state.toolTraces.length > 0 ? (
        <details className="mx-4 mt-3 rounded-md border border-dashed border-amber-500/50 bg-amber-500/5 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
          <summary className="cursor-pointer font-medium">
            Tool traces ({state.toolTraces.length})
          </summary>
          <div className="mt-2 max-h-40 space-y-1 overflow-y-auto font-mono">
            {state.toolTraces.map((trace, index) => (
              <p key={`${trace.tool_name}:${trace.phase}:${index}`}>
                {trace.tool_name} | {trace.phase} | status={trace.status} | duration=
                {trace.duration_ms ?? "n/a"}ms | output={trace.output_bytes}B | args=
                {trace.args_preview}
              </p>
            ))}
          </div>
        </details>
      ) : null}

      <div className={cn("flex-1 overflow-y-auto p-4", state.status === "streaming" ? "opacity-100" : "")}>
        <MessageList
          messages={state.messages}
          streamingContent={state.streamingContent}
        />
        {isAgentThinking ? (
          <output
            aria-live="polite"
            className="mt-3 flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground"
          >
            <Spinner />
            <span>Agent is thinking...</span>
          </output>
        ) : null}
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
        {movementDraft ? (
          <StockMovementDraftConfirmation
            token={token}
            draft={movementDraft}
            disabled={state.status === "streaming"}
            onCancel={() => setMovementDraft(null)}
            onSuccess={handleMovementDraftSuccess}
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
        focusRequestKey={latestMessageScrollKey}
        receiptUploadDisabled={!companyId || state.status === "streaming" || hasActiveExpenseDraft}
        receiptUploadLoading={isExtractingExpense}
        onReceiptSelected={handleReceiptSelected}
        onSend={sendMessage}
      />
    </div>
  );
}

