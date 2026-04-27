"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { signOut, SessionProvider, useSession } from "next-auth/react";
import { ThemeProvider } from "next-themes";
import { useEffect, useState, type ReactNode } from "react";
import { routes } from "@/shared/config/routes";
import { Toaster } from "@/shared/ui/toaster";

function SessionErrorHandler() {
  const { data: session } = useSession();

  useEffect(() => {
    if (session?.error === "RefreshAccessTokenError") {
      void signOut({ callbackUrl: routes.login });
    }
  }, [session?.error]);

  return null;
}

export function Providers({ children }: Readonly<{ children: ReactNode }>) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  return (
    <SessionProvider>
      <SessionErrorHandler />
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
        <QueryClientProvider client={queryClient}>
          {children}
          <Toaster />
        </QueryClientProvider>
      </ThemeProvider>
    </SessionProvider>
  );
}

