"use client";

import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { getSession, signOut, useSession } from "next-auth/react";
import { useQueryClient } from "@tanstack/react-query";

import { useConversation, useConversations } from "@/entities/conversation/api/queries";
import { getConversationDisplayTitle } from "@/entities/conversation/model/display-title";
import { MessageList } from "@/entities/conversation/ui/message-list";
import { expenseKeys } from "@/entities/expense/model/query-keys";
import { invoiceKeys } from "@/entities/invoice/model/query-keys";
import { inventoryKeys } from "@/entities/inventory/model/query-keys";
import { partnerKeys } from "@/entities/partner/model/query-keys";
import { streamAgentMessage } from "@/features/send-message/api/stream-message";
import {
  confirmSalesInvoiceDraft,
  confirmSalesInvoiceInventoryReview,
  createSalesInvoiceInventoryPreview,
} from "@/features/send-message/api/sales-invoice-workflow";
import {
  confirmExtractedExpense,
  confirmInventoryImportForExpense,
  createDocumentIntake,
  updateInventoryImportPreviewLines,
} from "@/features/send-message/api/receipt-expense";
import { ExpenseDraftConfirmation } from "@/features/send-message/ui/expense-draft-confirmation";
import { MessageInput } from "@/features/send-message/ui/message-input";
import { SalesInvoiceDraftConfirmation } from "@/features/send-message/ui/sales-invoice-draft-confirmation";
import { SalesInvoiceInventoryConfirmation } from "@/features/send-message/ui/sales-invoice-inventory-confirmation";
import { SalesInvoiceRequestDialog } from "@/features/send-message/ui/sales-invoice-request-dialog";
import { SalesInvoiceSuggestedKickoffCard } from "@/features/send-message/ui/sales-invoice-suggested-kickoff-card";
import { SupplierInvoiceInventoryConfirmation } from "@/features/send-message/ui/supplier-invoice-inventory-confirmation";
import { conversationKeys } from "@/entities/conversation/model/query-keys";
import { documentKeys } from "@/features/upload-document/api/mutations";
import {
  parseWorkflowSuggestion,
  toSalesInvoiceRequestInitialValues,
  toSalesInvoicePreviewPayload,
} from "@/features/send-message/model/chat-suggestion-schema";
import { buildSalesInvoiceConfirmationMessage } from "@/features/send-message/model/sales-invoice-confirmation-message";
import type {
  ConfirmSalesInvoiceInventoryPayload,
  CreateSalesInvoiceInventoryPreviewInput,
} from "@/features/send-message/model/sales-invoice-workflow-schema";
import type { InvoiceCreate } from "@/entities/invoice/model/types";
import { useChatStore } from "@/shared/store/chat-store";
import { useNotificationStore } from "@/shared/store/notification-store";
import { ApiError } from "@/shared/api/errors";
import { Alert } from "@/shared/ui/alert";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/cn";
import { routes } from "@/shared/config/routes";
import { buildExpenseConfirmationMessage } from "@/features/send-message/model/expense-confirmation-message";
import { receiptUploadSchema, getReceiptUploadErrorMessage, type ExpenseDraftFormValues } from "@/features/send-message/model/receipt-expense-schema";
import { Spinner } from "@/shared/ui/spinner";
import type { RecordStockMovementInput } from "@/features/record-stock-movement/model/schema";
import { StockMovementDraftConfirmation } from "@/features/record-stock-movement/ui/stock-movement-draft-confirmation";
import type { ImportPreviewLine, StockMovement } from "@/entities/inventory/model/types";

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
      documentReviewStatus: "idle",
      expenseDraft: null,
      inventoryImportPreview: null,
      unknownDocumentReview: null,
      documentReviewError: null,
      toolTraces: [],
      activeWorkflow: null,
      salesInvoiceStatus: "idle",
      salesInvoiceInventoryReview: null,
      salesInvoiceDraft: null,
      salesInvoiceCreated: null,
      salesInvoiceError: null,
      salesInvoiceSuggestion: null,
    }),
    [],
  );
  const [state, dispatch] = useReducer(chatReducer, initialState);
  const [movementDraft, setMovementDraft] = useState<RecordStockMovementInput | null>(null);
  const [isSalesInvoiceRequestOpen, setIsSalesInvoiceRequestOpen] = useState(false);
  const [suggestedPreviewPending, setSuggestedPreviewPending] = useState(false);
  const isDevelopment = process.env.NODE_ENV === "development";
  const historyLoadedForConversation = useRef<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const conversationsMenuRef = useRef<HTMLDetailsElement | null>(null);

  const isExtractingDocument = state.documentReviewStatus === "loading";
  const isConfirmingInventory = state.documentReviewStatus === "confirming_inventory";
  const isConfirmingExpense = state.documentReviewStatus === "confirming_expense";
  const isConfirmingSalesInvoiceInventory = state.salesInvoiceStatus === "confirming_sales_invoice_inventory";
  const isConfirmingSalesInvoice = state.salesInvoiceStatus === "confirming_sales_invoice";
  const isPreparingSalesInvoiceInventory = state.salesInvoiceStatus === "loading_sales_invoice_inventory";
  const isExpenseConfirmed = state.documentReviewStatus === "confirmed";
  const isAgentThinking =
    state.status === "streaming" && state.streamingContent.length === 0;
  const hasActiveDocumentReview = !["idle", "confirmed", "error"].includes(
    state.documentReviewStatus,
  );
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

  function getWorkflowErrorMessage(error: unknown): string {
    if (error instanceof ApiError) {
      return error.message;
    }
    if (error instanceof Error) {
      return error.message;
    }
    return "Sales invoice workflow request failed.";
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
        if (event.event === "workflow_suggestion") {
          const suggestion = parseWorkflowSuggestion(event.data);
          if (suggestion?.workflow === "sales_invoice_inventory") {
            dispatch({ type: "SALES_INVOICE_SUGGESTION_READY", payload: suggestion });
            setSuggestedPreviewPending(true);
            setIsSalesInvoiceRequestOpen(true);
          }
          continue;
        }
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

  async function handleSalesInvoicePreview(payload: CreateSalesInvoiceInventoryPreviewInput["payload"]) {
    const activeToken = await resolveActiveToken();
    if (!activeToken || !companyId) {
      addNotification("Assign this agent to a company before starting the sales invoice workflow.", "error");
      return;
    }

    dispatch({ type: "SALES_INVOICE_PREVIEW_LOADING" });
    try {
      const response = await createSalesInvoiceInventoryPreview({
        agentId,
        token: activeToken,
        payload,
      });
      dispatch({ type: "SALES_INVOICE_INVENTORY_READY", payload: response });
    } catch (error) {
      const message = getWorkflowErrorMessage(error);
      dispatch({ type: "SALES_INVOICE_PREVIEW_FAILED", payload: message });
      addNotification(message, "error");
    }
  }

  async function handleSalesInvoiceInventoryConfirm(values: ConfirmSalesInvoiceInventoryPayload) {
    const activeToken = await resolveActiveToken();
    if (!activeToken) {
      addNotification("You must be logged in to confirm inventory lines.", "error");
      return;
    }

    dispatch({ type: "SALES_INVOICE_INVENTORY_CONFIRMING" });
    try {
      const response = await confirmSalesInvoiceInventoryReview({
        agentId,
        token: activeToken,
        payload: values,
      });
      dispatch({ type: "SALES_INVOICE_READY", payload: response });
    } catch (error) {
      const message = getWorkflowErrorMessage(error);
      dispatch({
        type: "SALES_INVOICE_INVENTORY_CONFIRMATION_FAILED",
        payload: message,
      });
      addNotification(message, "error");
    }
  }

  async function handleSalesInvoiceDraftConfirm(invoiceDraft: InvoiceCreate) {
    const activeToken = await resolveActiveToken();
    if (!activeToken) {
      addNotification("You must be logged in to confirm sales invoices.", "error");
      return;
    }

    dispatch({ type: "SALES_INVOICE_CONFIRMING" });
    try {
      const response = await confirmSalesInvoiceDraft({
        agentId,
        token: activeToken,
        invoiceDraft,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: invoiceKeys.all }),
        queryClient.invalidateQueries({ queryKey: inventoryKeys.all }),
        queryClient.invalidateQueries({ queryKey: partnerKeys.all }),
        queryClient.invalidateQueries({ queryKey: conversationKeys.list(conversationListParams) }),
      ]);
      dispatch({ type: "SALES_INVOICE_CONFIRMATION_SUCCEEDED", payload: response });
      dispatch({
        type: "APPEND_ASSISTANT_MESSAGE",
        payload: {
          content: buildSalesInvoiceConfirmationMessage(response),
          metadata: { kind: "sales_invoice_confirmation" },
        },
      });
      addNotification(`Sales invoice created: ${response.invoice.invoice_number}`, "success");
    } catch (error) {
      const message = getWorkflowErrorMessage(error);
      dispatch({ type: "SALES_INVOICE_CONFIRMATION_FAILED", payload: message });
      addNotification(message, "error");
    }
  }

  async function handleSalesInvoiceSuggestedKickoff() {
    if (!state.salesInvoiceSuggestion) return;
    const payload = toSalesInvoicePreviewPayload(state.salesInvoiceSuggestion);
    if (!payload) {
      setSuggestedPreviewPending(true);
      setIsSalesInvoiceRequestOpen(true);
      return;
    }
    await handleSalesInvoicePreview(payload);
  }

  function handleSalesInvoiceSuggestionStart() {
    if (state.salesInvoiceSuggestion) {
      void handleSalesInvoiceSuggestedKickoff();
      return;
    }
    setSuggestedPreviewPending(false);
    setIsSalesInvoiceRequestOpen(true);
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

  async function handleDocumentSelected(file: File) {
    if (!token) {
      addNotification("You must be logged in to upload documents.", "error");
      return;
    }
    if (!companyId) {
      addNotification("Assign this agent to a company before uploading documents.", "error");
      return;
    }
    if (state.status === "streaming") {
      addNotification("Please wait for the current response to finish before uploading a document.", "info");
      return;
    }

    const validation = receiptUploadSchema.safeParse({ file, source_document_type: "auto" });
    if (!validation.success) {
      addNotification(validation.error.issues[0]?.message ?? "Invalid receipt file.", "error");
      return;
    }

    dispatch({ type: "DOCUMENT_INTAKE_LOADING" });
    try {
      const response = await createDocumentIntake({
        agentId,
        file,
        requestedType: "auto",
        token,
      });
      dispatch({ type: "DOCUMENT_INTAKE_READY", payload: response });
    } catch (error) {
      const errorMessage = getReceiptUploadErrorMessage(error);
      dispatch({ type: "DOCUMENT_INTAKE_ERROR", payload: errorMessage });
      addNotification(errorMessage, "error");
    }
  }

  async function handleInventoryConfirm(lines: ImportPreviewLine[], values: ExpenseDraftFormValues) {
    if (!token) {
      addNotification("You must be logged in to confirm inventory imports.", "error");
      return;
    }
    if (!state.inventoryImportPreview) {
      addNotification("No inventory preview is available to confirm.", "error");
      return;
    }

    dispatch({ type: "INVENTORY_IMPORT_CONFIRMING" });
    try {
      await updateInventoryImportPreviewLines({
        previewId: state.inventoryImportPreview.id,
        lines,
        token,
      });

      const response = await confirmInventoryImportForExpense({
        agentId,
        previewId: state.inventoryImportPreview.id,
        draft: values,
        token,
      });

      await queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
      dispatch({ type: "INVENTORY_IMPORT_CONFIRMED_FOR_EXPENSE", payload: response });
      addNotification("Inventory import confirmed. Review and confirm the expense next.", "success");
    } catch (error) {
      const errorMessage = getReceiptUploadErrorMessage(error);
      dispatch({ type: "INVENTORY_IMPORT_CONFIRMATION_FAILED", payload: errorMessage });
      throw error;
    }
  }

  async function handleDraftConfirm(values: ExpenseDraftFormValues) {
    if (!token) {
      addNotification("You must be logged in to confirm expenses.", "error");
      return;
    }

    const fallbackStatus =
      state.documentReviewStatus === "supplier_expense_ready"
        ? "supplier_expense_ready"
        : "receipt_expense_ready";
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
      dispatch({ type: "EXPENSE_CONFIRMATION_FAILED", payload: { draft: values, fallbackStatus } });
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

      {state.salesInvoiceSuggestion && state.salesInvoiceStatus === "idle" ? (
        <SalesInvoiceSuggestedKickoffCard
          suggestion={state.salesInvoiceSuggestion}
          disabled={state.status === "streaming"}
          onDismiss={() => dispatch({ type: "SALES_INVOICE_SUGGESTION_DISMISSED" })}
          onStart={handleSalesInvoiceSuggestionStart}
        />
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
        {isExtractingDocument ? (
          <output
            className="mt-3 flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground"
          >
            <Spinner />
            <span>Reading document and preparing review...</span>
          </output>
        ) : null}
        {(state.documentReviewStatus === "supplier_inventory_ready" ||
          state.documentReviewStatus === "confirming_inventory") &&
        state.expenseDraft &&
        state.inventoryImportPreview ? (
          <SupplierInvoiceInventoryConfirmation
            draft={state.expenseDraft}
            preview={state.inventoryImportPreview}
            disabled={state.status === "streaming"}
            confirming={isConfirmingInventory}
            onCancel={() => dispatch({ type: "DOCUMENT_REVIEW_CLEAR" })}
            onConfirmWithLines={handleInventoryConfirm}
          />
        ) : null}
        {(state.documentReviewStatus === "receipt_expense_ready" ||
          state.documentReviewStatus === "supplier_expense_ready" ||
          state.documentReviewStatus === "confirming_expense" ||
          state.documentReviewStatus === "confirmed") &&
        state.expenseDraft ? (
          <ExpenseDraftConfirmation
            draft={state.expenseDraft}
            disabled={state.status === "streaming"}
            confirming={isConfirmingExpense}
            confirmed={isExpenseConfirmed}
            onCancel={() => dispatch({ type: "DOCUMENT_REVIEW_CLEAR" })}
            onConfirm={handleDraftConfirm}
          />
        ) : null}
        {state.documentReviewStatus === "unknown_ready" && state.unknownDocumentReview ? (
          <div className="mx-3 mb-3 mt-3">
            <Alert>
              <div className="space-y-2 text-sm">
                <p className="font-medium">Document needs manual review</p>
                <p>
                  This upload was classified as {state.unknownDocumentReview.classification.document_type}. Please
                  review it manually outside the expense workflow.
                </p>
                {state.unknownDocumentReview.warnings.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
                    {state.unknownDocumentReview.warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </Alert>
          </div>
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
        {(state.salesInvoiceStatus === "sales_invoice_inventory_ready" ||
          state.salesInvoiceStatus === "confirming_sales_invoice_inventory") &&
        state.salesInvoiceInventoryReview ? (
          <SalesInvoiceInventoryConfirmation
            review={state.salesInvoiceInventoryReview}
            confirming={isConfirmingSalesInvoiceInventory}
            disabled={state.status === "streaming"}
            onCancel={() => dispatch({ type: "SALES_INVOICE_CLEAR" })}
            onConfirm={handleSalesInvoiceInventoryConfirm}
          />
        ) : null}
        {state.salesInvoiceDraft ? (
          <SalesInvoiceDraftConfirmation
            review={state.salesInvoiceDraft}
            confirming={isConfirmingSalesInvoice}
            confirmed={state.salesInvoiceStatus === "sales_invoice_confirmed"}
            disabled={state.status === "streaming"}
            onCancel={() => dispatch({ type: "SALES_INVOICE_CLEAR" })}
            onConfirm={handleSalesInvoiceDraftConfirm}
          />
        ) : null}
        <div ref={bottomRef} />
      </div>

      {state.documentReviewStatus === "error" && state.documentReviewError ? (
        <div className="px-4 pt-3">
          <Alert variant="destructive">{state.documentReviewError}</Alert>
        </div>
      ) : null}
      {state.salesInvoiceStatus === "error" && state.salesInvoiceError ? (
        <div className="px-4 pt-3">
          <Alert variant="destructive">{state.salesInvoiceError}</Alert>
        </div>
      ) : null}

      <MessageInput
        disabled={
          state.status === "streaming" ||
          isConfirmingInventory ||
          isConfirmingExpense ||
          isPreparingSalesInvoiceInventory ||
          isConfirmingSalesInvoiceInventory ||
          isConfirmingSalesInvoice
        }
        focusRequestKey={latestMessageScrollKey}
        receiptUploadDisabled={!companyId || state.status === "streaming" || hasActiveDocumentReview}
        receiptUploadLoading={isExtractingDocument}
        onSalesInvoiceRequest={() => setIsSalesInvoiceRequestOpen(true)}
        salesInvoiceRequestDisabled={!companyId || state.status === "streaming" || hasActiveDocumentReview}
        onReceiptSelected={handleDocumentSelected}
        onSend={sendMessage}
      />
      <SalesInvoiceRequestDialog
        open={isSalesInvoiceRequestOpen}
        disabled={
          state.status === "streaming" ||
          isPreparingSalesInvoiceInventory ||
          isConfirmingSalesInvoiceInventory ||
          isConfirmingSalesInvoice
        }
        onOpenChange={(nextOpen) => {
          setIsSalesInvoiceRequestOpen(nextOpen);
          if (!nextOpen) {
            setSuggestedPreviewPending(false);
          }
        }}
        initialPayload={
          suggestedPreviewPending && state.salesInvoiceSuggestion
            ? toSalesInvoiceRequestInitialValues(state.salesInvoiceSuggestion)
            : null
        }
        onSubmit={async (payload) => {
          setSuggestedPreviewPending(false);
          await handleSalesInvoicePreview(payload);
        }}
      />
    </div>
  );
}

