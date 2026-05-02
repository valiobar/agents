import type { Message } from "@/entities/conversation/model/types";
import type { ExpenseDraft } from "@/entities/expense/model/types";

export interface ChatState {
  messages: Message[];
  streamingContent: string;
  status: "idle" | "streaming" | "error";
  error: string | null;
  expenseDraftStatus: "idle" | "loading" | "ready" | "confirming" | "confirmed" | "error";
  expenseDraft: ExpenseDraft | null;
  expenseDraftError: string | null;
}

export type ChatAction =
  | { type: "LOAD_HISTORY"; payload: Message[] }
  | { type: "RESET" }
  | { type: "SEND_MESSAGE"; payload: string }
  | { type: "STREAM_TOKEN"; payload: string }
  | { type: "STREAM_COMPLETE" }
  | { type: "STREAM_ERROR"; payload: string }
  | { type: "EXPENSE_DRAFT_LOADING" }
  | { type: "EXPENSE_DRAFT_READY"; payload: ExpenseDraft }
  | { type: "EXPENSE_DRAFT_ERROR"; payload: string }
  | { type: "EXPENSE_DRAFT_CLEAR" }
  | { type: "EXPENSE_CONFIRMING" }
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
        expenseDraftStatus: "idle",
        expenseDraft: null,
        expenseDraftError: null,
      };
    case "RESET":
      return {
        messages: [],
        streamingContent: "",
        status: "idle",
        error: null,
        expenseDraftStatus: "idle",
        expenseDraft: null,
        expenseDraftError: null,
      };
    case "SEND_MESSAGE": {
      const clearConfirmedDraft = state.expenseDraftStatus === "confirmed";
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
              expenseDraftStatus: "idle" as const,
              expenseDraft: null,
              expenseDraftError: null,
            }
          : {}),
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
    case "EXPENSE_DRAFT_LOADING":
      return {
        ...state,
        expenseDraftStatus: "loading",
        expenseDraft: null,
        expenseDraftError: null,
      };
    case "EXPENSE_CONFIRMING":
      return {
        ...state,
        expenseDraftStatus: "confirming",
        expenseDraftError: null,
      };
    case "EXPENSE_DRAFT_READY":
      return {
        ...state,
        expenseDraftStatus: "ready",
        expenseDraft: action.payload,
        expenseDraftError: null,
      };
    case "EXPENSE_DRAFT_ERROR":
      return {
        ...state,
        expenseDraftStatus: "error",
        expenseDraft: null,
        expenseDraftError: action.payload,
      };
    case "EXPENSE_DRAFT_CLEAR":
      return {
        ...state,
        expenseDraftStatus: "idle",
        expenseDraft: null,
        expenseDraftError: null,
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
        expenseDraftStatus: "confirmed",
        expenseDraftError: null,
      };
    default:
      return state;
  }
}

