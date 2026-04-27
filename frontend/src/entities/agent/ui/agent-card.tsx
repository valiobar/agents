"use client";

import type { ReactNode } from "react";

import { Badge } from "@/shared/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/ui/card";

import type { Agent } from "../model/types";

export function AgentCard({
  agent,
  companyName,
  companySelector,
  actions,
}: Readonly<{ agent: Agent; companyName?: string; companySelector?: ReactNode; actions?: ReactNode }>) {
  return (
    <Card className="hover:border-foreground/20">
      <CardHeader className="space-y-2">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="line-clamp-1 text-lg">{agent.name}</CardTitle>
          <Badge variant="secondary" className="shrink-0">
            {agent.agent_type}
          </Badge>
        </div>
        {agent.description ? (
          <CardDescription className="line-clamp-2">{agent.description}</CardDescription>
        ) : (
          <CardDescription className="text-muted-foreground/70">No description</CardDescription>
        )}
      </CardHeader>

      <CardContent className="text-xs text-muted-foreground">
        {companySelector ? (
          <div className="mb-3">{companySelector}</div>
        ) : (
          <div className="mb-3">
            <span className="font-medium text-foreground/80">Company: </span>
            <span>{companyName ?? "Unassigned"}</span>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="font-medium text-foreground/80">{agent.config.provider}</span>
          {agent.config.model ? <span>{agent.config.model}</span> : <span>default model</span>}
          <span>temp {agent.config.temperature}</span>
        </div>
        {actions ? <div className="mt-4 flex justify-end gap-2">{actions}</div> : null}
      </CardContent>
    </Card>
  );
}

