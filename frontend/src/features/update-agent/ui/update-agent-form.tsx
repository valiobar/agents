"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCompanies } from "@/entities/company/api/queries";
import type { Agent } from "@/entities/agent/model/types";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

import { useUpdateAgent } from "../api/mutations";
import { updateAgentSchema, type UpdateAgentInput } from "../model/schema";

export interface UpdateAgentFormProps {
  agent: Agent;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const UNASSIGNED_COMPANY_VALUE = "__unassigned__";

const PROVIDERS: Array<UpdateAgentInput["config"]["provider"]> = [
  "openai",
  "anthropic",
  "deepseek",
  "ollama",
];

export function UpdateAgentForm({ agent, onSuccess, onCancel }: Readonly<UpdateAgentFormProps>) {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const updateAgent = useUpdateAgent(session?.accessToken);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<UpdateAgentInput>({
    resolver: zodResolver(updateAgentSchema),
    defaultValues: {
      name: agent.name,
      description: agent.description,
      company_id: agent.company_id,
      config: {
        provider: agent.config.provider,
        model: agent.config.model,
        temperature: agent.config.temperature,
        system_prompt_override: agent.config.system_prompt_override,
      },
    },
  });

  async function onSubmit(values: UpdateAgentInput) {
    setError(null);
    try {
      await updateAgent.mutateAsync({ agentId: agent.id, input: values });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to update agent. Please try again.");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {!companies.isLoading && !companies.data?.length ? (
          <EmptyState
            title="No companies yet"
            description="Keep this agent unassigned for now. Add a company later to enable company-scoped tools and document retrieval."
          />
        ) : null}

        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl>
                <Input placeholder="My Accountant" autoComplete="off" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="company_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Company</FormLabel>
              <Select
                value={field.value ?? UNASSIGNED_COMPANY_VALUE}
                onValueChange={(value) =>
                  field.onChange(value === UNASSIGNED_COMPANY_VALUE ? null : value)
                }
                disabled={companies.isLoading}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Assign a company" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value={UNASSIGNED_COMPANY_VALUE}>Unassigned</SelectItem>
                  {companies.data?.map((company) => (
                    <SelectItem key={company.id} value={company.id}>
                      {company.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Optional, but required for company document retrieval and invoice creation tools.
              </p>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Optional. What should this agent help you with?"
                  className="min-h-[96px]"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="config.provider"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Provider</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {PROVIDERS.map((provider) => (
                      <SelectItem key={provider} value={provider}>
                        {provider}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="config.temperature"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Temperature</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    max={2}
                    value={field.value ?? ""}
                    onChange={(e) =>
                      field.onChange(e.target.value === "" ? "" : e.target.valueAsNumber)
                    }
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="config.model"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Model override</FormLabel>
              <FormControl>
                <Input
                  placeholder="Optional. e.g. gpt-4o-mini"
                  autoComplete="off"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="config.system_prompt_override"
          render={({ field }) => (
            <FormItem>
              <FormLabel>System prompt override</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Optional. Provide custom system instructions for this agent."
                  className="min-h-[120px]"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex items-center justify-end gap-2">
          {onCancel ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                form.reset();
                setError(null);
                onCancel();
              }}
              disabled={updateAgent.isPending}
            >
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={updateAgent.isPending}>
            {updateAgent.isPending ? "Saving..." : "Save changes"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
