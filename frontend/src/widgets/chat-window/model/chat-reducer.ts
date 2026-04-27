import type { Message } from "@/entities/conversation/model/types";

export interface ChatState {
  messages: Message[];
  streamingContent: string;
  status: "idle" | "streaming" | "error";
  error: string | null;
}

export type ChatAction =
  | { type: "LOAD_HISTORY"; payload: Message[] }
  | { type: "RESET" }
  | { type: "SEND_MESSAGE"; payload: string }
  | { type: "STREAM_TOKEN"; payload: string }
  | { type: "STREAM_COMPLETE" }
  | { type: "STREAM_ERROR"; payload: string };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "LOAD_HISTORY":
      return {
        ...state,
        messages: action.payload,
        streamingContent: "",
        status: "idle",
        error: null,
      };
    case "RESET":
      return {
        messages: [],
        streamingContent: "",
        status: "idle",
        error: null,
      };
    case "SEND_MESSAGE":
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
      };
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
  }
}

