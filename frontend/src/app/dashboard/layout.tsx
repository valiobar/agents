import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { routes } from "@/shared/config/routes";
import { authOptions } from "@/shared/lib/auth";
import { Sidebar } from "@/widgets/sidebar/ui/sidebar";
import { Topbar } from "@/widgets/sidebar/ui/topbar";

export default async function DashboardLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken || session.error === "RefreshAccessTokenError") {
    redirect(routes.login);
  }

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="min-h-screen md:pl-64">
        <Topbar />
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}

