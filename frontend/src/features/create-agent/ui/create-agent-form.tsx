"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useCompanies } from "@/entities/company/api/queries";
import { ApiError } from "@/shared/api/errors";
import { cn } from "@/shared/lib/cn";
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

import { useCreateAgent } from "../api/mutations";
import { createAgentSchema, type CreateAgentInput } from "../model/schema";

export interface CreateAgentFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

const PROVIDERS: Array<CreateAgentInput["config"]["provider"]> = [
  "openai",
  "anthropic",
  "deepseek",
  "ollama",
];
const AGENT_TYPES: Array<{
  value: CreateAgentInput["agent_type"];
  label: string;
  description: string;
  disabled?: boolean;
  badge?: string;
}> = [
  {
    value: "accountant",
    label: "Accountant",
    description: "Financial tools for invoices, expenses, and summaries.",
  },
  {
    value: "inventory",
    label: "Inventory",
    description: "Stock tracking, item search, and movement workflows.",
  },
  {
    value: "router",
    label: "Router",
    description:
      "Classifies each chat turn and delegates to accountant, inventory, or general help.",
  },
];

export function CreateAgentForm({ onSuccess, onCancel }: Readonly<CreateAgentFormProps>) {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const createAgent = useCreateAgent(session?.accessToken);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<CreateAgentInput>({
    resolver: zodResolver(createAgentSchema),
    defaultValues: {
      name: "",
      description: null,
      agent_type: "accountant",
      company_id: null,
      config: {
        provider: "openai",
        model: null,
        temperature: 0.3,
        system_prompt_override: null,
      },
    },
    mode: "onSubmit",
  });
  const selectedAgentType = form.watch("agent_type");

  async function onSubmit(values: CreateAgentInput) {
    setError(null);
    try {
      await createAgent.mutateAsync(values);
      form.reset();
      onSuccess?.();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        return;
      }
      setError("Unable to create agent. Please try again.");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        {!companies.isLoading && !companies.data?.length ? (
          <EmptyState
            title="No companies yet"
            description="You can still create an unassigned agent. Add a company later to enable company-scoped tools and document retrieval."
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
          name="agent_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Agent type</FormLabel>
              <FormControl>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {AGENT_TYPES.map((agentType) => (
                    <button
                      key={agentType.value}
                      type="button"
                      className={cn(
                        "flex rounded-lg border p-3 text-left transition-colors",
                        agentType.disabled
                          ? "cursor-not-allowed opacity-70"
                          : "cursor-pointer hover:border-muted-foreground/40",
                        selectedAgentType === agentType.value && "border-primary bg-primary/5",
                      )}
                      aria-pressed={selectedAgentType === agentType.value}
                      disabled={agentType.disabled}
                      onClick={() => {
                        if (agentType.disabled) return;
                        field.onChange(agentType.value);
                        if (
                          agentType.value === "router" &&
                          form.getValues("config.temperature") === 0.3
                        ) {
                          form.setValue("config.temperature", 0.1, { shouldDirty: true });
                        }
                      }}
                    >
                      <span className="space-y-1">
                        <span className="flex items-center gap-2 text-sm font-medium">
                          {agentType.label}
                          {agentType.badge ? (
                            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                              {agentType.badge}
                            </span>
                          ) : null}
                        </span>
                        <span className="text-xs text-muted-foreground">{agentType.description}</span>
                      </span>
                    </button>
                  ))}
                </div>
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
                value={field.value ?? ""}
                onValueChange={(value) => field.onChange(value || null)}
                disabled={companies.isLoading}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Assign a company" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {companies.data?.map((company) => (
                    <SelectItem key={company.id} value={company.id}>
                      {company.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Optional, but required for company document retrieval and invoice creation tools.
                For a router, assigning a company limits delegation to specialists compatible with
                that company scope.
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
                    {PROVIDERS.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p}
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
              disabled={createAgent.isPending}
            >
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={createAgent.isPending}>
            {createAgent.isPending ? "Creating…" : "Create agent"}
          </Button>
        </div>
      </form>
    </Form>
  );
}

