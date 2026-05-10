import type { Message } from "@/entities/conversation/model/types";
import type {
  ConfirmInventoryImportForExpenseResponse,
  DocumentIntakeResponse,
  ExpenseDraft,
  UnknownDocumentReviewResponse,
} from "@/entities/expense/model/types";
import type { InventoryImportPreview } from "@/entities/inventory/model/types";
import type { ToolTracePayload } from "@/shared/api/sse";

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
    };

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
      };
    case "SEND_MESSAGE": {
      const clearConfirmedDraft = state.documentReviewStatus === "confirmed";
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
      };
    }
    case "STREAM_TOKEN":
      console.log("STREAM_TOKEN", action.payload);
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
    default:
      return state;
  }
}

