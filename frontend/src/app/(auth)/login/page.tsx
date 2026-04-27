import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { LoginForm } from "@/features/auth/login/ui/login-form";
import { routes } from "@/shared/config/routes";
import { authOptions } from "@/shared/lib/auth";

export default async function LoginPage() {
  const session = await getServerSession(authOptions);
  if (session?.accessToken) redirect(routes.dashboard);

  return <LoginForm />;
}

