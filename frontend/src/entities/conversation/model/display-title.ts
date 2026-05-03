import type { Conversation } from "./types";

const DEFAULT_MAX_TITLE_LENGTH = 48;

function normalizeTitleSource(value: string): string {
  return value.replaceAll(/\s+/g, " ").trim();
}

export function getConversationDisplayTitle(
  conversation: Conversation,
  maxLength = DEFAULT_MAX_TITLE_LENGTH,
): string {
  const latestMessage = [...conversation.messages]
    .reverse()
    .find((message) => normalizeTitleSource(message.content));

  const source =
    normalizeTitleSource(latestMessage?.content ?? "") ||
    normalizeTitleSource(conversation.title ?? "") ||
    "Untitled conversation";

  if (source.length <= maxLength) {
    return source;
  }

  return `${source.slice(0, maxLength).trimEnd()}...`;
}
