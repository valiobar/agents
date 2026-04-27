"use client";

import { useSession } from "next-auth/react";
import { useMemo } from "react";

import { useAgent } from "@/entities/agent/api/queries";
import { useCompanies } from "@/entities/company/api/queries";
import { EmptyState } from "@/shared/ui/empty-state";
import { Spinner } from "@/shared/ui/spinner";
import { ChatWindow } from "@/widgets/chat-window/ui/chat-window";

export default function AgentDetailPage({
  params,
}: Readonly<{
  params: { id: string };
}>) {
  const { data: session, status } = useSession();
  const agent = useAgent(params.id, session?.accessToken);
  const companies = useCompanies(session?.accessToken);

  const companyName = useMemo(() => {
    if (!agent.data?.company_id) return "Unassigned";
    return companies.data?.find((company) => company.id === agent.data?.company_id)?.name ?? agent.data.company_id;
  }, [agent.data?.company_id, companies.data]);

  if (status === "loading" || agent.isLoading || companies.isLoading) {
    return (
      <section className="space-y-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner />
          <span>Loading agent...</span>
        </div>
      </section>
    );
  }

  if (agent.isError || !agent.data) {
    return (
      <section className="space-y-6">
        <EmptyState
          title="Unable to load agent"
          description="Please go back and try again."
        />
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{agent.data.name}</h1>
        <p className="mt-1 text-sm text-muted-foreground">Company scope: {companyName}</p>
        {agent.data.description ? (
          <p className="mt-1 text-sm text-muted-foreground">{agent.data.description}</p>
        ) : null}
      </div>

      <ChatWindow agentId={agent.data.id} companyId={agent.data.company_id} />
    </section>
  );
}

