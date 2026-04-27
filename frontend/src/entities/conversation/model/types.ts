export type MessageRole = "user" | "assistant" | "system" | "tool";

export interface Message {
  role: MessageRole;
  content: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  agent_id: string;
  company_id: string | null;
  title: string | null;
  messages: Message[];
  created_at: string;
  updated_at: string;
}

