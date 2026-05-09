"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";

import { useCreateInventoryItem } from "../api/mutations";
import { createInventoryItemSchema, type CreateInventoryItemInput } from "../model/schema";

export interface CreateInventoryItemFormProps {
  companyId: string;
  token: string;
  onSuccess?: () => void;
}

export function CreateInventoryItemForm({
  companyId,
  token,
  onSuccess,
}: Readonly<CreateInventoryItemFormProps>) {
  const createInventoryItem = useCreateInventoryItem(token);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<CreateInventoryItemInput>({
    resolver: zodResolver(createInventoryItemSchema),
    defaultValues: {
      company_id: companyId,
      sku: "",
      name: "",
      description: null,
      category: null,
      barcode: null,
      aliases: [],
      unit: "pcs",
      selling_price: null,
      reorder_point: null,
      target_stock_level: null,
      supplier_partner_id: null,
    },
  });

  useEffect(() => {
    form.setValue("company_id", companyId);
  }, [companyId, form]);

  async function onSubmit(values: CreateInventoryItemInput) {
    setError(null);
    try {
      await createInventoryItem.mutateAsync(values);
      form.reset({
        company_id: companyId,
        sku: "",
        name: "",
        description: null,
        category: null,
        barcode: null,
        aliases: [],
        unit: values.unit || "pcs",
        selling_price: null,
        reorder_point: null,
        target_stock_level: null,
        supplier_partner_id: null,
      });
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to create inventory item. Please try again.");
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
        <input type="hidden" {...form.register("company_id")} />

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="sku"
            render={({ field }) => (
              <FormItem>
                <FormLabel>SKU</FormLabel>
                <FormControl>
                  <Input placeholder="ITEM-001" autoComplete="off" {...field} />
                </FormControl>
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
                  <Input placeholder="Wireless Mouse" autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="unit"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Unit</FormLabel>
                <FormControl>
                  <Input placeholder="pcs" autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="category"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Category</FormLabel>
                <FormControl>
                  <Input
                    placeholder="electronics"
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
            name="barcode"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Barcode</FormLabel>
                <FormControl>
                  <Input
                    placeholder="4901234567890"
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
            name="supplier_partner_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Supplier partner ID</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Optional supplier partner ID"
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
            name="selling_price"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Selling price</FormLabel>
                <FormControl>
                  <Input
                    placeholder="0.00"
                    inputMode="decimal"
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
            name="reorder_point"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Reorder point</FormLabel>
                <FormControl>
                  <Input
                    placeholder="10"
                    inputMode="decimal"
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
            name="target_stock_level"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Target stock level</FormLabel>
                <FormControl>
                  <Input
                    placeholder="50"
                    inputMode="decimal"
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
          name="aliases"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Aliases (comma-separated)</FormLabel>
              <FormControl>
                <Input
                  placeholder="wireless mouse, bluetooth mouse"
                  value={field.value.join(", ")}
                  onChange={(e) => {
                    const aliases = e.target.value
                      .split(",")
                      .map((alias) => alias.trim())
                      .filter(Boolean);
                    field.onChange(aliases);
                  }}
                />
              </FormControl>
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
                  className="min-h-[88px]"
                  placeholder="Optional notes about this item"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex justify-end">
          <Button type="submit" disabled={createInventoryItem.isPending}>
            {createInventoryItem.isPending ? "Creating..." : "Create item"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
