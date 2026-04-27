"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useForm } from "react-hook-form";
import { useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

import { useCreatePartner } from "../api/mutations";
import { partnerSchema, type PartnerInput } from "../model/schema";

export interface CreatePartnerFormProps {
  defaultCompanyId?: string;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const PARTNER_KINDS: Array<{ label: string; value: PartnerInput["kind"] }> = [
  { label: "Client", value: "client" },
  { label: "Supplier", value: "supplier" },
  { label: "Both", value: "both" },
  { label: "Other", value: "other" },
];

export function CreatePartnerForm({
  defaultCompanyId = "",
  onSuccess,
  onCancel,
}: Readonly<CreatePartnerFormProps>) {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const createPartner = useCreatePartner(session?.accessToken);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<PartnerInput>({
    resolver: zodResolver(partnerSchema),
    defaultValues: {
      company_id: defaultCompanyId,
      kind: "client",
      name: "",
      registration_number: "",
      vat_number: null,
      city: "",
      country: "Bulgaria",
      address: "",
      accountable_person: "",
      email: null,
      phone: null,
      notes: null,
    },
  });

  async function onSubmit(values: PartnerInput) {
    setError(null);
    try {
      await createPartner.mutateAsync(values);
      form.reset({ ...form.getValues(), name: "", registration_number: "", vat_number: null });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to create partner. Please try again.");
    }
  }

  if (!companies.isLoading && !companies.data?.length) {
    return (
      <EmptyState
        title="Create a company first"
        description="Partners must belong to a company before they can be used in invoices."
      />
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="company_id"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Company</FormLabel>
                <Select value={field.value} onValueChange={field.onChange} disabled={companies.isLoading}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select company" />
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
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="kind"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Kind</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select kind" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {PARTNER_KINDS.map((kind) => (
                      <SelectItem key={kind.value} value={kind.value}>
                        {kind.label}
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
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Name</FormLabel>
                <FormControl>
                  <Input placeholder="Client Ltd" autoComplete="organization" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="registration_number"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Registration number</FormLabel>
                <FormControl>
                  <Input placeholder="123456789" autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="vat_number"
            render={({ field }) => (
              <FormItem>
                <FormLabel>VAT number</FormLabel>
                <FormControl>
                  <Input
                    placeholder="BG123456789"
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
            name="city"
            render={({ field }) => (
              <FormItem>
                <FormLabel>City</FormLabel>
                <FormControl>
                  <Input placeholder="Sofia" autoComplete="address-level2" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="country"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Country</FormLabel>
                <FormControl>
                  <Input autoComplete="country-name" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="address"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Address</FormLabel>
                <FormControl>
                  <Textarea placeholder="Street, building, floor" className="min-h-[72px]" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="accountable_person"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Accountable person</FormLabel>
                <FormControl>
                  <Input placeholder="Ivan Ivanov" autoComplete="name" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="office@example.com"
                    autoComplete="email"
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
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Phone</FormLabel>
                <FormControl>
                  <Input
                    placeholder="+359..."
                    autoComplete="tel"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Notes</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Optional internal notes"
                  className="min-h-[88px]"
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
            <Button type="button" variant="outline" onClick={onCancel} disabled={createPartner.isPending}>
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={createPartner.isPending}>
            {createPartner.isPending ? "Creating..." : "Create partner"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
