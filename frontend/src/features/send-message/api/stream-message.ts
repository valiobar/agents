import { env } from "@/shared/config/env";
import { streamSSE } from "@/shared/api/sse";

export interface StreamMessageInput {
  agentId: string;
  message: string;
  conversationId?: string | null;
  token: string;
}

export async function* streamAgentMessage(input: StreamMessageInput) {
  yield* streamSSE(`${env.publicGatewayUrl}/agents/${input.agentId}/chat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${input.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message: input.message,
      conversation_id: input.conversationId ?? null,
    }),
  });
}

