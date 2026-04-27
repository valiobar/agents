import { apiClient } from "@/shared/api/client";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export function registerUser(input: RegisterRequest): Promise<TokenResponse> {
  return apiClient.post<TokenResponse>("/auth/register", input);
}

