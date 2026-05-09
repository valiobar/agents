"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import { useInventoryLocations, useInventorySearch } from "@/entities/inventory/api/queries";
import type { InventorySearchMatch } from "@/entities/inventory/model/types";
import { ApiError } from "@/shared/api/errors";
import { useDebouncedValue } from "@/shared/lib/use-debounced-value";
import { Button } from "@/shared/ui/button";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";

import { useRecordStockMovement } from "../api/mutations";
import { recordStockMovementSchema, type RecordStockMovementInput } from "../model/schema";

const MOVEMENT_TYPES = [
  { value: "receipt", label: "Receipt" },
  { value: "issue", label: "Issue" },
  { value: "adjustment", label: "Adjustment" },
  { value: "transfer_in", label: "Transfer In" },
  { value: "transfer_out", label: "Transfer Out" },
  { value: "return", label: "Return" },
] as const;

export interface RecordStockMovementFormProps {
  companyId: string;
  token: string;
  onSuccess?: () => void;
}

function normalizeInventorySearchQuery(value: string): string {
  return value
    .normalize("NFKD")
    .replaceAll(/[\u200B-\u200D\uFEFF]/g, "")
    .replaceAll(/[\u2010-\u2015\u2212]/g, "-")
    .trim()
    .replaceAll(/\s+/g, " ");
}

function getInventorySuggestionValue(match: InventorySearchMatch): string {
  const label = match.description || match.name;
  const discriminator = match.sku?.trim() || match.item_id;
  return `${label} [${discriminator}]`;
}

export function RecordStockMovementForm({
  companyId,
  token,
  onSuccess,
}: Readonly<RecordStockMovementFormProps>) {
  const [error, setError] = useState<string | null>(null);
  const [itemSearchValue, setItemSearchValue] = useState("");
  const recordMovement = useRecordStockMovement(token);
  const locations = useInventoryLocations(companyId, token);
  const itemSuggestionsId = "record-stock-movement-item-suggestions";
  const debouncedItemSearch = useDebouncedValue(itemSearchValue, 250);
  const normalizedItemSearch = normalizeInventorySearchQuery(debouncedItemSearch);
  const inventorySearch = useInventorySearch(
    token,
    {
      company_id: companyId,
      query: normalizedItemSearch,
      include_stock: false,
      min_confidence: 0.5,
      limit: 20,
    },
    { enabled: normalizedItemSearch.length >= 2 },
  );
  const searchMatches = inventorySearch.data?.matches ?? [];

  const form = useForm<RecordStockMovementInput>({
    resolver: zodResolver(recordStockMovementSchema),
    defaultValues: {
      company_id: companyId,
      item_id: "",
      location_id: "",
      movement_type: "receipt",
      quantity_delta: "",
      reason: null,
    },
  });

  useEffect(() => {
    form.setValue("company_id", companyId);
    setItemSearchValue("");
    form.setValue("item_id", "", { shouldValidate: false });
  }, [companyId, form]);

  async function onSubmit(values: RecordStockMovementInput) {
    setError(null);
    try {
      await recordMovement.mutateAsync(values);
      form.reset({
        company_id: companyId,
        item_id: "",
        location_id: "",
        movement_type: "receipt",
        quantity_delta: "",
        reason: null,
      });
      setItemSearchValue("");
      onSuccess?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unable to record stock movement. Please try again.");
    }
  }

  function handleItemSearchChange(value: string, onChange: (value: string) => void) {
    setItemSearchValue(value);
    const selectedMatch = searchMatches.find((match) => getInventorySuggestionValue(match) === value);
    if (selectedMatch) {
      onChange(selectedMatch.item_id);
      return;
    }
    onChange("");
  }

  function getItemSearchStatusMessage(): { message: string; tone: "muted" | "destructive" } | null {
    if (!companyId) {
      return { message: "Select a company first", tone: "muted" };
    }
    if (!token) {
      return { message: "Session unavailable, reopen dialog", tone: "muted" };
    }
    if (normalizeInventorySearchQuery(itemSearchValue).length < 2) {
      return { message: "Type at least 2 characters to search", tone: "muted" };
    }
    if (inventorySearch.isLoading || inventorySearch.isFetching) {
      return { message: "Searching...", tone: "muted" };
    }
    if (inventorySearch.error) {
      return {
        message: inventorySearch.error instanceof ApiError ? inventorySearch.error.message : "Search failed",
        tone: "destructive",
      };
    }
    if (!searchMatches.length) {
      return { message: "No matches", tone: "muted" };
    }
    return null;
  }

  const itemSearchStatus = getItemSearchStatusMessage();

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
        <input type="hidden" {...form.register("company_id")} />

        <FormField
          control={form.control}
          name="movement_type"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Movement Type</FormLabel>
              <Select onValueChange={field.onChange} value={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select movement type" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {MOVEMENT_TYPES.map((movementType) => (
                    <SelectItem key={movementType.value} value={movementType.value}>
                      {movementType.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="item_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Item</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Start typing to search inventory item"
                    autoComplete="off"
                    list={itemSuggestionsId}
                    value={itemSearchValue}
                    onChange={(event) => {
                      handleItemSearchChange(event.target.value, field.onChange);
                    }}
                  />
                </FormControl>
                <datalist id={itemSuggestionsId}>
                  {searchMatches.map((match) => (
                    <option
                      key={match.item_id}
                      value={getInventorySuggestionValue(match)}
                      label={`${match.sku ?? "NO-SKU"} - ${match.name}`}
                    />
                  ))}
                </datalist>
                {itemSearchStatus ? (
                  <p className={`mt-2 text-xs ${itemSearchStatus.tone === "destructive" ? "text-destructive" : "text-muted-foreground"}`}>
                    {itemSearchStatus.message}
                  </p>
                ) : null}
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="location_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Location</FormLabel>
                <Select
                  disabled={locations.isLoading || !locations.data?.locations.length}
                  onValueChange={field.onChange}
                  value={field.value || undefined}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue
                        placeholder={locations.isLoading ? "Loading locations..." : "Select location"}
                      />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {locations.data?.locations.map((location) => (
                      <SelectItem key={location.id} value={location.id}>
                        {location.name}
                        {location.is_default ? " (default)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="quantity_delta"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Quantity</FormLabel>
                <FormControl>
                  <Input placeholder="10" inputMode="decimal" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="reason"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Reason</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Monthly restock"
                    value={field.value ?? ""}
                    onChange={(event) => field.onChange(event.target.value)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="flex justify-end">
          <Button type="submit" disabled={recordMovement.isPending}>
            {recordMovement.isPending ? "Recording..." : "Record movement"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
