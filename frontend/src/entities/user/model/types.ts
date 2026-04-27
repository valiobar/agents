export type AuthProvider = "credentials" | "google" | "both";

export interface User {
  id: string;
  email: string;
  name: string;
  image: string | null;
  auth_provider: AuthProvider;
}

