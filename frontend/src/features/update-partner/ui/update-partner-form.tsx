"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import type { Partner } from "@/entities/partner/model/types";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

import { useDeletePartner, useUpdatePartner } from "../api/mutations";
import { updatePartnerSchema, type UpdatePartnerInput } from "../model/schema";

interface UpdatePartnerFormProps {
  partner: Partner;
  onSuccess?: () => void;
  onCancel?: () => void;
}

const PARTNER_KINDS: Array<{ label: string; value: UpdatePartnerInput["kind"] }> = [
  { label: "Client", value: "client" },
  { label: "Supplier", value: "supplier" },
  { label: "Both", value: "both" },
  { label: "Other", value: "other" },
];

export function UpdatePartnerForm({ partner, onSuccess, onCancel }: Readonly<UpdatePartnerFormProps>) {
  const { data: session } = useSession();
  const updatePartner = useUpdatePartner(session?.accessToken);
  const deletePartner = useDeletePartner(session?.accessToken);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<UpdatePartnerInput>({
    resolver: zodResolver(updatePartnerSchema),
    defaultValues: {
      kind: partner.kind,
      name: partner.name,
      registration_number: partner.registration_number,
      vat_number: partner.vat_number,
      city: partner.city,
      country: partner.country,
      address: partner.address,
      accountable_person: partner.accountable_person,
      email: partner.email,
      phone: partner.phone,
      notes: partner.notes,
    },
  });

  async function onSubmit(values: UpdatePartnerInput) {
    setError(null);
    try {
      await updatePartner.mutateAsync({
        partnerId: partner.id,
        companyId: partner.company_id,
        input: values,
      });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to update partner. Please try again.");
    }
  }

  async function handleDelete() {
    setError(null);
    try {
      await deletePartner.mutateAsync({ partnerId: partner.id, companyId: partner.company_id });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to delete partner. Please try again.");
    }
  }

  const pending = updatePartner.isPending || deletePartner.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
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
                  <Input autoComplete="organization" {...field} />
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
                  <Input autoComplete="off" {...field} />
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
                  <Input value={field.value ?? ""} onChange={(e) => field.onChange(e.target.value)} />
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
                  <Input autoComplete="address-level2" {...field} />
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
                  <Textarea className="min-h-[72px]" {...field} />
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
                  <Input autoComplete="name" {...field} />
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

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button type="button" variant="outline" onClick={handleDelete} disabled={pending}>
            {deletePartner.isPending ? "Deleting..." : "Delete partner"}
          </Button>
          <div className="flex items-center justify-end gap-2">
            {onCancel ? (
              <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
                Cancel
              </Button>
            ) : null}
            <Button type="submit" disabled={pending}>
              {updatePartner.isPending ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </div>
      </form>
    </Form>
  );
}
