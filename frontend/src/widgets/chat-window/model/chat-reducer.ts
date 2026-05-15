import type { Message } from "@/entities/conversation/model/types";
import type {
  ConfirmInventoryImportForExpenseResponse,
  DocumentIntakeResponse,
  ExpenseDraft,
  UnknownDocumentReviewResponse,
} from "@/entities/expense/model/types";
import type { InventoryImportPreview } from "@/entities/inventory/model/types";
import type { ToolTracePayload } from "@/shared/api/sse";
import type {
  SalesInvoiceCreatedResponse,
  SalesInvoiceInventoryReview,
  SalesInvoiceReview,
} from "@/features/send-message/model/sales-invoice-workflow-schema";
import type { SalesInvoiceWorkflowSuggestion } from "@/features/send-message/model/chat-suggestion-schema";

interface SalesInvoiceActiveWorkflow {
  workflow: "sales_invoice_inventory";
  step:
    | "loading_inventory"
    | "inventory_review"
    | "confirming_inventory"
    | "invoice_review"
    | "confirming_invoice"
    | "created"
    | "error";
  payload: SalesInvoiceInventoryReview | SalesInvoiceReview | SalesInvoiceCreatedResponse | null;
  error: string | null;
}

interface SalesWorkflowState {
  salesInvoiceSuggestion: SalesInvoiceWorkflowSuggestion | null;
  activeWorkflow: SalesInvoiceActiveWorkflow | null;
  salesInvoiceStatus:
    | "idle"
    | "loading_sales_invoice_inventory"
    | "sales_invoice_inventory_ready"
    | "confirming_sales_invoice_inventory"
    | "sales_invoice_ready"
    | "confirming_sales_invoice"
    | "sales_invoice_confirmed"
    | "error";
  salesInvoiceInventoryReview: SalesInvoiceInventoryReview | null;
  salesInvoiceDraft: SalesInvoiceReview | null;
  salesInvoiceCreated: SalesInvoiceCreatedResponse | null;
  salesInvoiceError: string | null;
}

export interface ChatState {
  messages: Message[];
  streamingContent: string;
  status: "idle" | "streaming" | "error";
  error: string | null;
  documentReviewStatus:
    | "idle"
    | "loading"
    | "receipt_expense_ready"
    | "supplier_inventory_ready"
    | "supplier_expense_ready"
    | "unknown_ready"
    | "confirming_inventory"
    | "confirming_expense"
    | "confirmed"
    | "error";
  expenseDraft: ExpenseDraft | null;
  inventoryImportPreview: InventoryImportPreview | null;
  unknownDocumentReview: UnknownDocumentReviewResponse | null;
  documentReviewError: string | null;
  toolTraces: ToolTracePayload[];
  activeWorkflow: SalesInvoiceActiveWorkflow | null;
  salesInvoiceStatus: SalesWorkflowState["salesInvoiceStatus"];
  salesInvoiceInventoryReview: SalesInvoiceInventoryReview | null;
  salesInvoiceDraft: SalesInvoiceReview | null;
  salesInvoiceCreated: SalesInvoiceCreatedResponse | null;
  salesInvoiceError: string | null;
  salesInvoiceSuggestion: SalesInvoiceWorkflowSuggestion | null;
}

const initialSalesWorkflowState: SalesWorkflowState = {
  salesInvoiceSuggestion: null,
  activeWorkflow: null,
  salesInvoiceStatus: "idle",
  salesInvoiceInventoryReview: null,
  salesInvoiceDraft: null,
  salesInvoiceCreated: null,
  salesInvoiceError: null,
};

function clearSalesWorkflowState(overrides?: Partial<SalesWorkflowState>): SalesWorkflowState {
  return {
    ...initialSalesWorkflowState,
    ...overrides,
  };
}

export type ChatAction =
  | { type: "LOAD_HISTORY"; payload: Message[] }
  | { type: "RESET" }
  | { type: "SEND_MESSAGE"; payload: string }
  | { type: "STREAM_TOKEN"; payload: string }
  | { type: "STREAM_COMPLETE" }
  | { type: "STREAM_ERROR"; payload: string }
  | { type: "DOCUMENT_INTAKE_LOADING" }
  | { type: "DOCUMENT_INTAKE_READY"; payload: DocumentIntakeResponse }
  | { type: "DOCUMENT_INTAKE_ERROR"; payload: string }
  | { type: "INVENTORY_IMPORT_CONFIRMING" }
  | { type: "INVENTORY_IMPORT_CONFIRMATION_FAILED"; payload: string }
  | { type: "INVENTORY_IMPORT_CONFIRMED_FOR_EXPENSE"; payload: ConfirmInventoryImportForExpenseResponse }
  | { type: "EXPENSE_CONFIRMING" }
  | {
      type: "EXPENSE_CONFIRMATION_FAILED";
      payload: {
        draft: ExpenseDraft;
        fallbackStatus: "receipt_expense_ready" | "supplier_expense_ready";
      };
    }
  | { type: "TOOL_TRACE"; payload: ToolTracePayload }
  | { type: "DOCUMENT_REVIEW_CLEAR" }
  | {
      type: "APPEND_ASSISTANT_MESSAGE";
      payload: { content: string; metadata?: Record<string, unknown>; createdAt?: string };
    }
  | {
      type: "EXPENSE_CONFIRMATION_SUCCEEDED";
      payload: { content: string; createdAt?: string };
    }
  | { type: "SALES_INVOICE_PREVIEW_LOADING" }
  | { type: "SALES_INVOICE_SUGGESTION_READY"; payload: SalesInvoiceWorkflowSuggestion }
  | { type: "SALES_INVOICE_SUGGESTION_DISMISSED" }
  | { type: "SALES_INVOICE_INVENTORY_READY"; payload: SalesInvoiceInventoryReview }
  | { type: "SALES_INVOICE_PREVIEW_FAILED"; payload: string }
  | { type: "SALES_INVOICE_INVENTORY_CONFIRMING" }
  | { type: "SALES_INVOICE_READY"; payload: SalesInvoiceReview }
  | { type: "SALES_INVOICE_INVENTORY_CONFIRMATION_FAILED"; payload: string }
  | { type: "SALES_INVOICE_CONFIRMING" }
  | { type: "SALES_INVOICE_CONFIRMATION_SUCCEEDED"; payload: SalesInvoiceCreatedResponse }
  | { type: "SALES_INVOICE_CONFIRMATION_FAILED"; payload: string }
  | { type: "SALES_INVOICE_CLEAR" };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "LOAD_HISTORY":
      return {
        ...state,
        messages: action.payload,
        streamingContent: "",
        status: "idle",
        error: null,
        documentReviewStatus: "idle",
        expenseDraft: null,
        inventoryImportPreview: null,
        unknownDocumentReview: null,
        documentReviewError: null,
        toolTraces: [],
        ...clearSalesWorkflowState(),
      };
    case "RESET":
      return {
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
        ...clearSalesWorkflowState(),
      };
    case "SEND_MESSAGE": {
      const clearConfirmedDraft = state.documentReviewStatus === "confirmed";
      const clearConfirmedSalesInvoice = state.salesInvoiceStatus === "sales_invoice_confirmed";
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            role: "user",
            content: action.payload,
            created_at: new Date().toISOString(),
            metadata: {},
          },
        ],
        streamingContent: "",
        status: "streaming",
        error: null,
        ...(clearConfirmedDraft
          ? {
              documentReviewStatus: "idle" as const,
              expenseDraft: null,
              inventoryImportPreview: null,
              unknownDocumentReview: null,
              documentReviewError: null,
            }
          : {}),
        ...(clearConfirmedSalesInvoice ? clearSalesWorkflowState() : {}),
      };
    }
    case "STREAM_TOKEN":
      return {
        ...state,
        streamingContent: state.streamingContent + action.payload,
      };
    case "STREAM_COMPLETE":
      return {
        ...state,
        messages: state.streamingContent
          ? [
              ...state.messages,
              {
                role: "assistant",
                content: state.streamingContent,
                created_at: new Date().toISOString(),
                metadata: {},
              },
            ]
          : state.messages,
        streamingContent: "",
        status: "idle",
        error: null,
      };
    case "STREAM_ERROR":
      return {
        ...state,
        status: "error",
        error: action.payload,
      };
    case "DOCUMENT_INTAKE_LOADING":
      return {
        ...state,
        documentReviewStatus: "loading",
        expenseDraft: null,
        inventoryImportPreview: null,
        unknownDocumentReview: null,
        documentReviewError: null,
      };
    case "DOCUMENT_INTAKE_READY":
      if (action.payload.type === "supplier_invoice_inventory_review") {
        return {
          ...state,
          documentReviewStatus: "supplier_inventory_ready",
          expenseDraft: action.payload.draft,
          inventoryImportPreview: action.payload.inventory_import_preview,
          unknownDocumentReview: null,
          documentReviewError: null,
        };
      }

      if (action.payload.type === "supplier_invoice_expense_review") {
        return {
          ...state,
          documentReviewStatus: "supplier_expense_ready",
          expenseDraft: action.payload.draft,
          inventoryImportPreview: null,
          unknownDocumentReview: null,
          documentReviewError: null,
        };
      }

      if (action.payload.type === "unknown_document_review") {
        return {
          ...state,
          documentReviewStatus: "unknown_ready",
          expenseDraft: null,
          inventoryImportPreview: null,
          unknownDocumentReview: action.payload,
          documentReviewError: null,
        };
      }

      return {
        ...state,
        documentReviewStatus: "receipt_expense_ready",
        expenseDraft: action.payload.draft,
        inventoryImportPreview: null,
        unknownDocumentReview: null,
        documentReviewError: null,
      };
    case "DOCUMENT_INTAKE_ERROR":
      return {
        ...state,
        documentReviewStatus: "error",
        expenseDraft: null,
        inventoryImportPreview: null,
        unknownDocumentReview: null,
        documentReviewError: action.payload,
      };
    case "INVENTORY_IMPORT_CONFIRMING":
      return {
        ...state,
        documentReviewStatus: "confirming_inventory",
        documentReviewError: null,
      };
    case "INVENTORY_IMPORT_CONFIRMATION_FAILED":
      return {
        ...state,
        documentReviewStatus: "supplier_inventory_ready",
        documentReviewError: action.payload,
      };
    case "INVENTORY_IMPORT_CONFIRMED_FOR_EXPENSE":
      return {
        ...state,
        documentReviewStatus: "supplier_expense_ready",
        expenseDraft: action.payload.draft,
        inventoryImportPreview: null,
        unknownDocumentReview: null,
        documentReviewError: null,
      };
    case "EXPENSE_CONFIRMING":
      return {
        ...state,
        documentReviewStatus: "confirming_expense",
        documentReviewError: null,
      };
    case "TOOL_TRACE":
      return {
        ...state,
        toolTraces: [...state.toolTraces, action.payload].slice(-50),
      };
    case "EXPENSE_CONFIRMATION_FAILED":
      return {
        ...state,
        documentReviewStatus: action.payload.fallbackStatus,
        expenseDraft: action.payload.draft,
        documentReviewError: null,
      };
    case "DOCUMENT_REVIEW_CLEAR":
      return {
        ...state,
        documentReviewStatus: "idle",
        expenseDraft: null,
        inventoryImportPreview: null,
        unknownDocumentReview: null,
        documentReviewError: null,
      };
    case "APPEND_ASSISTANT_MESSAGE":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            role: "assistant",
            content: action.payload.content,
            created_at: action.payload.createdAt ?? new Date().toISOString(),
            metadata: action.payload.metadata ?? {},
          },
        ],
      };
    case "EXPENSE_CONFIRMATION_SUCCEEDED":
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            role: "assistant",
            content: action.payload.content,
            created_at: action.payload.createdAt ?? new Date().toISOString(),
            metadata: { kind: "expense_confirmation" },
          },
        ],
        documentReviewStatus: "confirmed",
        documentReviewError: null,
      };
    case "SALES_INVOICE_PREVIEW_LOADING":
      return {
        ...state,
        ...clearSalesWorkflowState({
          salesInvoiceSuggestion: state.salesInvoiceSuggestion,
          activeWorkflow: {
            workflow: "sales_invoice_inventory",
            step: "loading_inventory",
            payload: null,
            error: null,
          },
          salesInvoiceStatus: "loading_sales_invoice_inventory",
        }),
      };
    case "SALES_INVOICE_INVENTORY_READY":
      return {
        ...state,
        ...clearSalesWorkflowState({
          salesInvoiceSuggestion: state.salesInvoiceSuggestion,
          activeWorkflow: {
            workflow: "sales_invoice_inventory",
            step: "inventory_review",
            payload: action.payload,
            error: null,
          },
          salesInvoiceStatus: "sales_invoice_inventory_ready",
          salesInvoiceInventoryReview: action.payload,
        }),
      };
    case "SALES_INVOICE_PREVIEW_FAILED":
      return {
        ...state,
        ...clearSalesWorkflowState({
          salesInvoiceSuggestion: state.salesInvoiceSuggestion,
          activeWorkflow: {
            workflow: "sales_invoice_inventory",
            step: "error",
            payload: null,
            error: action.payload,
          },
          salesInvoiceStatus: "error",
          salesInvoiceError: action.payload,
        }),
      };
    case "SALES_INVOICE_SUGGESTION_READY":
      return {
        ...state,
        salesInvoiceSuggestion: action.payload,
      };
    case "SALES_INVOICE_SUGGESTION_DISMISSED":
      return {
        ...state,
        salesInvoiceSuggestion: null,
      };
    case "SALES_INVOICE_INVENTORY_CONFIRMING":
      return {
        ...state,
        salesInvoiceStatus: "confirming_sales_invoice_inventory",
        activeWorkflow: {
          workflow: "sales_invoice_inventory",
          step: "confirming_inventory",
          payload: state.salesInvoiceInventoryReview,
          error: null,
        },
        salesInvoiceError: null,
      };
    case "SALES_INVOICE_READY":
      return {
        ...state,
        salesInvoiceStatus: "sales_invoice_ready",
        salesInvoiceDraft: action.payload,
        salesInvoiceCreated: null,
        salesInvoiceError: null,
        activeWorkflow: {
          workflow: "sales_invoice_inventory",
          step: "invoice_review",
          payload: action.payload,
          error: null,
        },
      };
    case "SALES_INVOICE_INVENTORY_CONFIRMATION_FAILED":
      return {
        ...state,
        salesInvoiceStatus: "sales_invoice_inventory_ready",
        salesInvoiceError: action.payload,
        activeWorkflow: {
          workflow: "sales_invoice_inventory",
          step: "inventory_review",
          payload: state.salesInvoiceInventoryReview,
          error: action.payload,
        },
      };
    case "SALES_INVOICE_CONFIRMING":
      return {
        ...state,
        salesInvoiceStatus: "confirming_sales_invoice",
        salesInvoiceError: null,
        activeWorkflow: {
          workflow: "sales_invoice_inventory",
          step: "confirming_invoice",
          payload: state.salesInvoiceDraft,
          error: null,
        },
      };
    case "SALES_INVOICE_CONFIRMATION_SUCCEEDED":
      return {
        ...state,
        salesInvoiceStatus: "sales_invoice_confirmed",
        salesInvoiceCreated: action.payload,
        salesInvoiceError: null,
        activeWorkflow: {
          workflow: "sales_invoice_inventory",
          step: "created",
          payload: action.payload,
          error: null,
        },
      };
    case "SALES_INVOICE_CONFIRMATION_FAILED":
      return {
        ...state,
        salesInvoiceStatus: "sales_invoice_ready",
        salesInvoiceError: action.payload,
        activeWorkflow: {
          workflow: "sales_invoice_inventory",
          step: "invoice_review",
          payload: state.salesInvoiceDraft,
          error: action.payload,
        },
      };
    case "SALES_INVOICE_CLEAR":
      return {
        ...state,
        ...clearSalesWorkflowState(),
      };
    default:
      return state;
  }
}

