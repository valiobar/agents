import type { NextAuthOptions, User } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import { env } from "@/shared/config/env";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

async function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  const response = await fetch(`${env.gatewayUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!response.ok) {
    throw new Error("Unable to refresh session");
  }

  return response.json() as Promise<TokenResponse>;
}

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  pages: {
    signIn: "/login",
  },
  providers: [
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const response = await fetch(`${env.gatewayUrl}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(credentials),
        });

        if (!response.ok) return null;
        const token = (await response.json()) as TokenResponse;

        const user: User = {
          id: credentials?.email ?? "user",
          email: credentials?.email,
          accessToken: token.access_token,
          refreshToken: token.refresh_token,
        };

        return user;
      },
    }),
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
  ],
  callbacks: {
    async signIn({ user, account }) {
      if (account?.provider !== "google") return true;
      if (!account.id_token) return false;

      const response = await fetch(`${env.gatewayUrl}/auth/oauth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: account.id_token }),
      });

      if (!response.ok) return false;
      const token = (await response.json()) as TokenResponse;

      user.accessToken = token.access_token;
      user.refreshToken = token.refresh_token;
      return true;
    },
    async jwt({ token, user }) {
      if (user?.accessToken) {
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.accessTokenExpires = Date.now() + 29 * 60 * 1000;
        token.error = undefined;
      }

      if (
        token.refreshToken &&
        token.accessTokenExpires &&
        Date.now() > token.accessTokenExpires
      ) {
        try {
          const refreshed = await refreshAccessToken(token.refreshToken);
          token.accessToken = refreshed.access_token;
          token.refreshToken = refreshed.refresh_token;
          token.accessTokenExpires = Date.now() + 29 * 60 * 1000;
          token.error = undefined;
        } catch {
          token.error = "RefreshAccessTokenError";
        }
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.error = token.error;
      return session;
    },
  },
};

