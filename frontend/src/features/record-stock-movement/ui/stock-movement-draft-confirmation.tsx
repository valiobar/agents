"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";

import type { InventoryItem, InventorySearchResponse, StockMovement } from "@/entities/inventory/model/types";
import { apiClient } from "@/shared/api/client";
import { ApiError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/shared/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";

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

export interface StockMovementDraftConfirmationProps {
  token: string | null;
  draft: RecordStockMovementInput;
  disabled?: boolean;
  onCancel: () => void;
  onSuccess: (movement: StockMovement, submittedValues: RecordStockMovementInput) => void;
}

export function StockMovementDraftConfirmation({
  token,
  draft,
  disabled = false,
  onCancel,
  onSuccess,
}: Readonly<StockMovementDraftConfirmationProps>) {
  const [error, setError] = useState<string | null>(null);
  const recordMovement = useRecordStockMovement(token);

  const form = useForm<RecordStockMovementInput>({
    resolver: zodResolver(recordStockMovementSchema),
    defaultValues: draft,
  });

  useEffect(() => {
    form.reset(draft);
    setError(null);
  }, [draft, form]);

  async function resolveItemId(companyId: string, itemIdentifier: string): Promise<string> {
    const trimmedIdentifier = itemIdentifier.trim();
    try {
      const item = await apiClient.get<InventoryItem>(`/inventory/items/${trimmedIdentifier}`, {
        token,
        params: { company_id: companyId },
      });
      return item.id;
    } catch (itemLookupError) {
      if (!(itemLookupError instanceof ApiError) || itemLookupError.status !== 404) {
        throw itemLookupError;
      }
    }

    const searchResponse = await apiClient.post<InventorySearchResponse>(
      "/inventory/search",
      {
        company_id: companyId,
        query: trimmedIdentifier,
        include_stock: false,
        min_confidence: 0.5,
        limit: 20,
      },
      { token },
    );

    const normalizedIdentifier = trimmedIdentifier.toLowerCase();
    const exactIdMatch = searchResponse.matches.find((match) => match.item_id === trimmedIdentifier);
    if (exactIdMatch) return exactIdMatch.item_id;

    const exactSkuMatch = searchResponse.matches.find(
      (match) => match.sku?.trim().toLowerCase() === normalizedIdentifier,
    );
    if (exactSkuMatch) return exactSkuMatch.item_id;

    const exactNameMatch = searchResponse.matches.find(
      (match) => match.name.trim().toLowerCase() === normalizedIdentifier,
    );
    if (exactNameMatch) return exactNameMatch.item_id;

    throw new ApiError(
      400,
      `No inventory item found for '${trimmedIdentifier}'. Use a valid item ID or SKU.`,
      null,
    );
  }

  async function handleSubmit(values: RecordStockMovementInput) {
    setError(null);
    try {
      const resolvedItemId = await resolveItemId(values.company_id, values.item_id);
      const payload: RecordStockMovementInput = {
        ...values,
        item_id: resolvedItemId,
      };
      const movement = await recordMovement.mutateAsync(payload);
      onSuccess(movement, payload);
    } catch (submissionError) {
      setError(
        submissionError instanceof ApiError
          ? submissionError.message
          : "Unable to record stock movement. Please try again.",
      );
    }
  }

  const isSubmitDisabled = disabled || recordMovement.isPending || !token;

  return (
    <Card className="mx-3 mb-3 mt-3 shadow-none">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Review stock movement draft</CardTitle>
        <CardDescription>
          Update any field if needed, then submit to record the movement.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form className="space-y-4" onSubmit={form.handleSubmit(handleSubmit)}>
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
                    <FormLabel>Item (ID or SKU)</FormLabel>
                    <FormControl>
                      <Input placeholder="SKU-001 or item_123" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="location_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Location ID</FormLabel>
                    <FormControl>
                      <Input placeholder="loc_default" {...field} />
                    </FormControl>
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
            {token ? null : (
              <p className="text-sm text-destructive">You must be logged in to submit stock movements.</p>
            )}

            <CardFooter className="px-0 pb-0 pt-2">
              <div className="flex w-full justify-end gap-2">
                <Button type="button" variant="outline" disabled={recordMovement.isPending} onClick={onCancel}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitDisabled}>
                  {recordMovement.isPending ? (
                    <>
                      <Spinner className="mr-2 h-3 w-3" />
                      Recording...
                    </>
                  ) : (
                    "Submit movement"
                  )}
                </Button>
              </div>
            </CardFooter>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
