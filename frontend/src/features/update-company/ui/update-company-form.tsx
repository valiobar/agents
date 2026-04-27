"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import type { Company } from "@/entities/company/model/types";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";

import { useDeleteCompany, useUpdateCompany } from "../api/mutations";
import { fileToLogoDataUrl, updateCompanySchema, type UpdateCompanyInput } from "../model/schema";

export interface UpdateCompanyFormProps {
  company: Company;
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function UpdateCompanyForm({ company, onSuccess, onCancel }: Readonly<UpdateCompanyFormProps>) {
  const { data: session } = useSession();
  const updateCompany = useUpdateCompany(session?.accessToken);
  const deleteCompany = useDeleteCompany(session?.accessToken);
  const [error, setError] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);

  const form = useForm<UpdateCompanyInput>({
    resolver: zodResolver(updateCompanySchema),
    defaultValues: {
      name: company.name,
      registration_number: company.registration_number,
      vat_number: company.vat_number,
      city: company.city,
      country: company.country,
      address: company.address,
      accountable_person: company.accountable_person,
      email: company.email,
      phone: company.phone,
      logo_data_url: company.logo_data_url,
      is_default: company.is_default,
    },
  });

  async function onSubmit(values: UpdateCompanyInput) {
    setError(null);
    try {
      await updateCompany.mutateAsync({ companyId: company.id, input: values });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to update company. Please try again.");
    }
  }

  async function handleDelete() {
    setError(null);
    try {
      await deleteCompany.mutateAsync(company.id);
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to delete company. Please try again.");
    }
  }

  async function handleLogoChange(file: File | undefined) {
    setLogoError(null);
    if (!file) {
      return;
    }

    try {
      form.setValue("logo_data_url", await fileToLogoDataUrl(file), { shouldDirty: true });
    } catch (e) {
      setLogoError(e instanceof Error ? e.message : "Unable to read logo file.");
    }
  }

  const pending = updateCompany.isPending || deleteCompany.isPending;

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Company name</FormLabel>
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

          <FormField
            control={form.control}
            name="is_default"
            render={({ field }) => (
              <FormItem className="flex items-center gap-2 pt-7">
                <FormControl>
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-input"
                    checked={field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                  />
                </FormControl>
                <FormLabel className="m-0">Default company</FormLabel>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="space-y-2">
          <FormLabel>Logo</FormLabel>
          <Input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            onChange={(e) => void handleLogoChange(e.target.files?.[0])}
          />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">PNG, JPEG, WebP, or GIF up to 256 KB.</p>
            {form.watch("logo_data_url") ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => form.setValue("logo_data_url", null, { shouldDirty: true })}
              >
                Remove logo
              </Button>
            ) : null}
          </div>
          {logoError ? <p className="text-sm text-destructive">{logoError}</p> : null}
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button type="button" variant="outline" onClick={handleDelete} disabled={pending}>
            {deleteCompany.isPending ? "Deleting..." : "Delete company"}
          </Button>
          <div className="flex items-center justify-end gap-2">
            {onCancel ? (
              <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
                Cancel
              </Button>
            ) : null}
            <Button type="submit" disabled={pending || Boolean(logoError)}>
              {updateCompany.isPending ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </div>
      </form>
    </Form>
  );
}
