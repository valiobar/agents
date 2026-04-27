"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useMemo } from "react";

import { useAgents } from "@/entities/agent/api/queries";
import type { Agent } from "@/entities/agent/model/types";
import { AgentCard } from "@/entities/agent/ui/agent-card";
import { useCompanies } from "@/entities/company/api/queries";
import { useUpdateAgent } from "@/features/update-agent/api/mutations";
import { UpdateAgentDialog } from "@/features/update-agent/ui/update-agent-dialog";
import { ApiError } from "@/shared/api/errors";
import { routes } from "@/shared/config/routes";
import { useNotificationStore } from "@/shared/store/notification-store";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";

const UNASSIGNED_COMPANY_VALUE = "__unassigned__";

export function AgentDashboard() {
  const { data: session, status } = useSession();
  const agents = useAgents(session?.accessToken);
  const companies = useCompanies(session?.accessToken);
  const updateAgent = useUpdateAgent(session?.accessToken);
  const { addNotification } = useNotificationStore();

  const companyNamesById = useMemo(
    () => new Map((companies.data ?? []).map((company) => [company.id, company.name])),
    [companies.data],
  );

  async function updateAgentCompany(agent: Agent, companyId: string | null) {
    try {
      await updateAgent.mutateAsync({
        agentId: agent.id,
        input: {
          name: agent.name,
          description: agent.description,
          company_id: companyId,
          config: agent.config,
        },
      });
      addNotification("Agent company scope updated.", "success");
    } catch (error) {
      addNotification(
        error instanceof ApiError ? error.message : "Unable to update agent company.",
        "error",
      );
    }
  }

  if (status === "loading" || agents.isLoading || companies.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        <span>Loading agents…</span>
      </div>
    );
  }

  if (agents.isError || companies.isError) {
    return (
      <EmptyState
        title="Unable to load agents"
        description="Please refresh the page and try again."
      />
    );
  }

  if (!agents.data?.length) {
    return (
      <EmptyState
        title="No agents yet"
        description="Create your first accountant agent."
      />
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {agents.data.map((agent) => {
        const companyName = agent.company_id
          ? (companyNamesById.get(agent.company_id) ?? agent.company_id)
          : undefined;

        return (
          <AgentCard
            key={agent.id}
            agent={agent}
            companyName={companyName}
            companySelector={
              <div className="space-y-1.5">
                <p className="font-medium text-foreground/80">Company scope</p>
                <Select
                  value={agent.company_id ?? UNASSIGNED_COMPANY_VALUE}
                  onValueChange={(value) =>
                    void updateAgentCompany(
                      agent,
                      value === UNASSIGNED_COMPANY_VALUE ? null : value,
                    )
                  }
                  disabled={updateAgent.isPending}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Select company" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={UNASSIGNED_COMPANY_VALUE}>Unassigned</SelectItem>
                    {companies.data?.map((company) => (
                      <SelectItem key={company.id} value={company.id}>
                        {company.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            }
            actions={
              <>
                <Button asChild variant="outline" size="sm">
                  <Link href={routes.agentDetail(agent.id)}>Open</Link>
                </Button>
                <UpdateAgentDialog agent={agent} />
              </>
            }
          />
        );
      })}
    </div>
  );
}

