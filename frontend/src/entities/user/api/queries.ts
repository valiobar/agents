import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import type { User } from "../model/types";

export const userKeys = {
  all: ["user"] as const,
  me: () => [...userKeys.all, "me"] as const,
};

export function useMe(token?: string | null) {
  return useQuery({
    queryKey: userKeys.me(),
    enabled: Boolean(token),
    queryFn: () => apiClient.get<User>("/auth/me", { token }),
  });
}

