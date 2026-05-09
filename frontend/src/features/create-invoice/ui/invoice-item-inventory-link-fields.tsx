"use client";

import { useEffect, useState } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";

import type { InventoryLocation, InventorySearchMatch, InventorySearchResponse } from "@/entities/inventory/model/types";
import { apiClient } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { useDebouncedValue } from "@/shared/lib/use-debounced-value";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";

import type { CreateInvoiceInput } from "../model/schema";

interface InvoiceItemInventoryLinkFieldsProps {
  form: UseFormReturn<CreateInvoiceInput>;
  index: number;
  rowId: string;
  token?: string | null;
  selectedCompanyId: string;
  freeTextOnly: boolean;
  onFreeTextOnlyChange: (next: boolean) => void;
  linkedItemId: string | null;
  inventoryLocations: InventoryLocation[];
  inventoryLocationsLoading: boolean;
  lowStockWarning: boolean;
  availableQuantity: number | null;
}

function parseQuantity(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeInventorySearchQuery(value: string): string {
  return value
    .normalize("NFKD")
    .replaceAll(/[\u200B-\u200D\uFEFF]/g, "")
    .replaceAll(/[\u2010-\u2015\u2212]/g, "-")
    .trim()
    .replaceAll(/\s+/g, " ");
}

function formatStock(match: InventorySearchMatch): string {
  const parsed = parseQuantity(match.available_quantity);
  return parsed === null ? "stock unavailable" : `${parsed.toFixed(4)} ${match.unit} available`;
}

function normalizeUnitPriceValue(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined) return null;
  const raw = typeof value === "number" ? String(value) : value.trim();
  if (!raw) return null;

  const parsed = Number.parseFloat(raw);
  if (!Number.isFinite(parsed) || parsed < 0) return null;

  return parsed.toFixed(4);
}

function getInventoryOptionValue(match: InventorySearchMatch): string {
  return match.description || match.name;
}

function getInventorySuggestionValue(match: InventorySearchMatch): string {
  const label = getInventoryOptionValue(match);
  const discriminator = match.sku?.trim() || match.item_id;
  return `${label} [${discriminator}]`;
}



export function InvoiceItemInventoryLinkFields({
  form,
  index,
  rowId,
  token,
  selectedCompanyId,
  freeTextOnly,
  onFreeTextOnlyChange,
  linkedItemId,
  inventoryLocations,
  inventoryLocationsLoading,
  lowStockWarning,
  availableQuantity,
}: Readonly<InvoiceItemInventoryLinkFieldsProps>) {
  const [searchMatches, setSearchMatches] = useState<InventorySearchMatch[]>([]);
  const [searchErrorMessage, setSearchErrorMessage] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const descriptionValue =
    useWatch({
      control: form.control,
      name: `items.${index}.description`,
    }) ?? "";
  const debouncedDescription = useDebouncedValue(descriptionValue, 250);
  const normalizedDescription = normalizeInventorySearchQuery(debouncedDescription);
  const hasSearchInput = normalizedDescription.length >= 2;
  const hasSearchContext = Boolean(selectedCompanyId && hasSearchInput);
  const canSearch = Boolean(token && !freeTextOnly && hasSearchContext);
  const shouldShowSearchMatches = canSearch && !searchLoading && !searchErrorMessage && searchMatches.length > 0;
  const inventorySuggestionsId = `items.${rowId}.inventory-suggestions`;

  useEffect(() => {
    if (!canSearch) {
      setSearchMatches([]);
      setSearchErrorMessage(null);
      setSearchLoading(false);
      return;
    }

    const controller = new AbortController();
    setSearchLoading(true);
    setSearchErrorMessage(null);

    apiClient
      .post<InventorySearchResponse>(
        "/inventory/search",
        {
          company_id: selectedCompanyId,
          query: normalizedDescription,
          include_stock: true,
          min_confidence: 0.5,
          limit: 20,
        },
        { token, signal: controller.signal },
      )
      .then((response) => {
        setSearchMatches(response.matches);
      })
      .catch((error: unknown) => {
        if (error instanceof Error && error.name === "AbortError") return;
        setSearchMatches([]);
        setSearchErrorMessage(error instanceof ApiError ? error.message : "Search failed");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setSearchLoading(false);
        }
      });

    return () => controller.abort();
  }, [canSearch, freeTextOnly, normalizedDescription, selectedCompanyId, token]);

  const shouldShowLocationControls = Boolean(!freeTextOnly && linkedItemId);

  function clearInventoryFields() {
    form.setValue(`items.${index}.inventory_item_id`, null, { shouldValidate: false });
    form.setValue(`items.${index}.inventory_location_id`, null, { shouldValidate: false });
    form.setValue(`items.${index}.stock_quantity`, null, { shouldValidate: false });
  }

  function resetSearchUiState() {
    setSearchMatches([]);
    setSearchErrorMessage(null);
    setSearchLoading(false);
  }

  function getRequestedStockQuantity(): string | null {
    const quantityValue = form.getValues(`items.${index}.quantity`);
    const parsed = parseQuantity(quantityValue);
    if (parsed === null || parsed <= 0) return null;
    return parsed.toFixed(4);
  }

  function selectInventoryMatch(match: InventorySearchMatch) {
    form.setValue(`items.${index}.inventory_item_id`, match.item_id, { shouldValidate: true });
    form.setValue(`items.${index}.inventory_location_id`, null, { shouldValidate: false });
    form.setValue(`items.${index}.description`, match.description || match.name, {
      shouldValidate: true,
    });
    form.setValue(`items.${index}.unit_label`, match.unit, { shouldValidate: true });
    form.setValue(`items.${index}.category`, match.category ?? null, { shouldValidate: false });
    const normalizedUnitPrice = normalizeUnitPriceValue(match.selling_price);
    if (normalizedUnitPrice !== null) {
      form.setValue(`items.${index}.unit_price`, normalizedUnitPrice, { shouldValidate: true });
    }

    form.setValue(`items.${index}.stock_quantity`, getRequestedStockQuantity(), {
      shouldValidate: false,
    });

    setSearchMatches([]);
    setSearchErrorMessage(null);
  }

  function handleDescriptionChange(value: string, onChange: (value: string) => void) {
    onChange(value);
    clearInventoryFields();

    const selectedMatch = searchMatches.find((match) => getInventorySuggestionValue(match) === value);
    if (selectedMatch) {
      selectInventoryMatch(selectedMatch);
    }
  }

  function getSearchStatusMessage(): { message: string; tone: "muted" | "destructive" } | null {
    if (!selectedCompanyId) {
      return { message: "Select a company first", tone: "muted" };
    }
    if (!token) {
      return { message: "Session unavailable, reopen dialog", tone: "muted" };
    }
    if (!hasSearchInput) {
      return { message: "Type at least 2 characters in description", tone: "muted" };
    }
    if (searchLoading) {
      return { message: "Searching...", tone: "muted" };
    }
    if (searchErrorMessage) {
      return { message: searchErrorMessage, tone: "destructive" };
    }
    if (canSearch && !shouldShowSearchMatches) {
      return { message: "No matches", tone: "muted" };
    }
    return null;
  }
  const searchStatus = getSearchStatusMessage();

  return (
    <>
      <FormField
        control={form.control}
        name={`items.${index}.description`}
        render={({ field }) => (
          <FormItem className="sm:col-span-2">
            <FormLabel>Description</FormLabel>
            <FormControl>
              <Input
                placeholder="Start typing to search inventory"
                autoComplete="off"
                list={freeTextOnly ? undefined : inventorySuggestionsId}
                value={field.value}
                onChange={(event) => {
                  handleDescriptionChange(event.target.value, field.onChange);
                }}
              />
            </FormControl>
            {freeTextOnly ? null : (
              <datalist id={inventorySuggestionsId}>
                {searchMatches.map((match) => (
                  <option
                    key={match.item_id}
                    value={getInventorySuggestionValue(match)}
                    label={`${match.sku ?? "NO-SKU"} - ${match.name} (${formatStock(match)})`}
                  />
                ))}
              </datalist>
            )}
            <div className="mt-3 flex items-center gap-2">
              <input
                id={`items.${rowId}.free-text-description`}
                type="checkbox"
                className="h-4 w-4 rounded border"
                checked={freeTextOnly}
                onChange={(event) => {
                  const next = event.target.checked;
                  onFreeTextOnlyChange(next);
                  if (next) {
                    clearInventoryFields();
                    resetSearchUiState();
                  }
                }}
              />
              <label htmlFor={`items.${rowId}.free-text-description`} className="text-xs text-muted-foreground">
                Do not use inventory, use free-text description
              </label>
            </div>
            {!freeTextOnly && linkedItemId ? (
              <button
                type="button"
                className="mt-2 text-xs text-muted-foreground underline underline-offset-2"
                onClick={() => {
                  clearInventoryFields();
                  resetSearchUiState();
                }}
              >
                Clear linked inventory item
              </button>
            ) : null}
            {!freeTextOnly && searchStatus ? (
              <p className={`mt-2 text-xs ${searchStatus.tone === "destructive" ? "text-destructive" : "text-muted-foreground"}`}>
                {searchStatus.message}
              </p>
            ) : null}
            <FormMessage />
          </FormItem>
        )}
      />

      {shouldShowLocationControls ? (
        <div className="grid gap-3 pt-3 sm:grid-cols-2">
          <FormField
            control={form.control}
            name={`items.${index}.inventory_location_id`}
            render={({ field }) => (
              <FormItem>
                <FormLabel className="text-xs">Location</FormLabel>
                <Select
                  value={field.value ?? "__none"}
                  onValueChange={(value) => {
                    const nextValue = value === "__none" ? null : value;
                    field.onChange(nextValue);
                    if (!linkedItemId) {
                      form.setValue(`items.${index}.stock_quantity`, null, {
                        shouldValidate: false,
                      });
                      return;
                    }
                    form.setValue(`items.${index}.stock_quantity`, getRequestedStockQuantity(), {
                      shouldValidate: false,
                    });
                  }}
                >
                  <FormControl>
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue placeholder="Select location" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="__none">Any location</SelectItem>
                    {inventoryLocationsLoading ? (
                      <SelectItem value="__loading" disabled>
                        Loading locations...
                      </SelectItem>
                    ) : null}
                    {inventoryLocations.map((location) => (
                      <SelectItem key={location.id} value={location.id}>
                        {location.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          {lowStockWarning ? (
            <p className="sm:col-span-2 text-xs text-destructive">
              Only {(availableQuantity ?? 0).toFixed(4)} units available. Sending this invoice will deduct stock.
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
