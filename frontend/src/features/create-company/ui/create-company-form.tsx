"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useSession } from "next-auth/react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";

import { useCreateCompany } from "../api/mutations";
import { companySchema, fileToLogoDataUrl, type CompanyInput } from "../model/schema";

export interface CreateCompanyFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function CreateCompanyForm({ onSuccess, onCancel }: Readonly<CreateCompanyFormProps>) {
  const { data: session } = useSession();
  const createCompany = useCreateCompany(session?.accessToken);
  const [error, setError] = useState<string | null>(null);
  const [logoError, setLogoError] = useState<string | null>(null);

  const form = useForm<CompanyInput>({
    resolver: zodResolver(companySchema),
    defaultValues: {
      name: "",
      registration_number: "",
      vat_number: null,
      city: "",
      country: "Bulgaria",
      address: "",
      accountable_person: "",
      email: null,
      phone: null,
      logo_data_url: null,
      is_default: false,
    },
  });

  async function onSubmit(values: CompanyInput) {
    setError(null);
    try {
      await createCompany.mutateAsync(values);
      form.reset();
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to create company. Please try again.");
    }
  }

  async function handleLogoChange(file: File | undefined) {
    setLogoError(null);
    if (!file) {
      form.setValue("logo_data_url", null);
      return;
    }

    try {
      form.setValue("logo_data_url", await fileToLogoDataUrl(file), { shouldDirty: true });
    } catch (e) {
      form.setValue("logo_data_url", null, { shouldDirty: true });
      setLogoError(e instanceof Error ? e.message : "Unable to read logo file.");
    }
  }

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
                  <Input placeholder="Acme Ltd" autoComplete="organization" {...field} />
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
          <p className="text-xs text-muted-foreground">PNG, JPEG, WebP, or GIF up to 256 KB.</p>
          {logoError ? <p className="text-sm text-destructive">{logoError}</p> : null}
        </div>

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
              disabled={createCompany.isPending}
            >
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={createCompany.isPending || Boolean(logoError)}>
            {createCompany.isPending ? "Creating..." : "Create company"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
