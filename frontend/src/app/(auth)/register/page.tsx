import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { RegisterForm } from "@/features/auth/register/ui/register-form";
import { routes } from "@/shared/config/routes";
import { authOptions } from "@/shared/lib/auth";

export default async function RegisterPage() {
  const session = await getServerSession(authOptions);
  if (session?.accessToken) redirect(routes.dashboard);

  return <RegisterForm />;
}

