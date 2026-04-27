"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Plus, Trash2 } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useMemo, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { useCompanies } from "@/entities/company/api/queries";
import { PartnerSelect } from "@/entities/partner/ui/partner-select";
import { ApiError } from "@/shared/api/errors";
import { formatCurrency, formatPercent } from "@/shared/lib/format";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/shared/ui/form";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Textarea } from "@/shared/ui/textarea";

import { useCreateInvoice } from "../api/mutations";
import { createInvoiceSchema, type CreateInvoiceInput } from "../model/schema";
import { calculateInvoicePreview } from "../model/totals";

export interface CreateInvoiceFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

const STATUSES: Array<CreateInvoiceInput["status"]> = ["draft", "sent", "paid", "overdue", "cancelled"];
const CURRENCIES: Array<CreateInvoiceInput["currency"]> = ["EUR", "BGN", "USD"];
const PAYMENT_METHODS: Array<{ label: string; value: CreateInvoiceInput["payment_method"] }> = [
  { label: "Bank transfer", value: "bank_transfer" },
  { label: "Cash", value: "cash" },
  { label: "Card", value: "card" },
  { label: "Other", value: "other" },
];

function emptyRecipient(): NonNullable<CreateInvoiceInput["recipient"]> {
  return {
    name: "",
    registration_number: "",
    vat_number: null,
    city: "",
    country: "Bulgaria",
    address: "",
    accountable_person: "",
    logo_data_url: null,
  };
}

export function CreateInvoiceForm({ onSuccess, onCancel }: Readonly<CreateInvoiceFormProps>) {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);
  const createInvoice = useCreateInvoice(session?.accessToken);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<CreateInvoiceInput>({
    resolver: zodResolver(createInvoiceSchema),
    defaultValues: {
      company_id: "",
      partner_id: null,
      recipient: emptyRecipient(),
      issue_date: new Date().toISOString().slice(0, 10),
      tax_event_date: new Date().toISOString().slice(0, 10),
      due_date: null,
      place_of_supply: "Bulgaria",
      payment_method: "bank_transfer",
      bank_name: null,
      bank_bic: null,
      bank_iban: null,
      vat_reason: null,
      recipient_name: null,
      compiler_name: null,
      original_label: "ОРИГИНАЛ",
      currency: "EUR",
      status: "draft",
      notes: null,
      items: [
        {
          description: "",
          quantity: "1",
          unit_label: "бр.",
          unit_price: "0",
          vat_rate: "0.20",
          category: null,
        },
      ],
    },
    mode: "onSubmit",
  });

  const items = form.watch("items");
  const selectedCompanyId = form.watch("company_id");
  const selectedPartnerId = form.watch("partner_id");
  const preview = useMemo(() => calculateInvoicePreview(items ?? []), [items]);

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  useEffect(() => {
    if (!form.getValues("company_id") && defaultCompanyId) {
      form.setValue("company_id", defaultCompanyId, { shouldValidate: true });
    }
  }, [defaultCompanyId, form]);

  const fieldArray = useFieldArray({
    control: form.control,
    name: "items",
  });

  async function onSubmit(values: CreateInvoiceInput) {
    setError(null);
    try {
      await createInvoice.mutateAsync(values);
      form.reset({
        ...form.getValues(),
        partner_id: null,
        recipient: emptyRecipient(),
        notes: null,
        items: [
          {
            description: "",
            quantity: "1",
            unit_label: "бр.",
            unit_price: "0",
            vat_rate: "0.20",
            category: null,
          },
        ],
      });
      onSuccess?.();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        return;
      }
      setError("Unable to create invoice. Please try again.");
    }
  }

  if (!companies.isLoading && !companies.data?.length) {
    return (
      <EmptyState
        title="Create a company first"
        description="Invoices must be issued from a company. Create a company before adding invoices."
      />
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="company_id"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Company</FormLabel>
                <Select
                  value={field.value}
                  onValueChange={(value) => {
                    field.onChange(value);
                    form.setValue("partner_id", null, { shouldValidate: true });
                    form.setValue("recipient", emptyRecipient(), { shouldValidate: false });
                  }}
                  disabled={companies.isLoading}
                >
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
            name="partner_id"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>Partner</FormLabel>
                <PartnerSelect
                  companyId={selectedCompanyId}
                  value={field.value}
                  onChange={(partnerId) => {
                    field.onChange(partnerId);
                    form.setValue("recipient", null, { shouldValidate: true });
                  }}
                  placeholder="Select an existing client"
                  disabled={!selectedCompanyId}
                />
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs text-muted-foreground">
                    Select a partner, or enter recipient details manually below.
                  </p>
                  {selectedPartnerId ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        field.onChange(null);
                        form.setValue("recipient", emptyRecipient(), { shouldValidate: true });
                      }}
                    >
                      Enter manually
                    </Button>
                  ) : null}
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          {selectedPartnerId ? null : (
            <div className="grid gap-4 rounded-lg border p-4 sm:col-span-2 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <h3 className="text-sm font-medium">Recipient details</h3>
                <p className="text-xs text-muted-foreground">
                  These fields are used only when no partner is selected.
                </p>
              </div>

              <FormField
                control={form.control}
                name="recipient.name"
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
                name="recipient.registration_number"
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
                name="recipient.vat_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>VAT number</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="BG123456789"
                        value={field.value ?? ""}
                        onChange={(e) => field.onChange(e.target.value || null)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="recipient.city"
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
                name="recipient.country"
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
                name="recipient.accountable_person"
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
                name="recipient.address"
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
            </div>
          )}

          <FormField
            control={form.control}
            name="issue_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Issue date</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="tax_event_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tax event date</FormLabel>
                <FormControl>
                  <Input type="date" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="due_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Due date</FormLabel>
                <FormControl>
                  <Input
                    type="date"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="place_of_supply"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Place of supply</FormLabel>
                <FormControl>
                  <Input placeholder="Bulgaria" autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="payment_method"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Payment method</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select method" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {PAYMENT_METHODS.map((method) => (
                      <SelectItem key={method.value} value={method.value}>
                        {method.label}
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
            name="currency"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Currency</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select currency" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {CURRENCIES.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
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
            name="status"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Status</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-medium">Line items</h3>
              <p className="text-xs text-muted-foreground">
                Preview totals are calculated in the browser; final totals come from the backend.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                fieldArray.append({
                  description: "",
                  quantity: "1",
                  unit_label: "бр.",
                  unit_price: "0",
                  vat_rate: "0.20",
                  category: null,
                })
              }
            >
              <Plus className="mr-2 h-4 w-4" />
              Add item
            </Button>
          </div>

          <div className="space-y-4">
            {fieldArray.fields.map((f, index) => (
              <div key={f.id} className="rounded-lg border p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="grid flex-1 gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name={`items.${index}.description`}
                      render={({ field }) => (
                        <FormItem className="sm:col-span-2">
                          <FormLabel>Description</FormLabel>
                          <FormControl>
                            <Input placeholder="Accounting consultation" autoComplete="off" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name={`items.${index}.quantity`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Quantity</FormLabel>
                          <FormControl>
                            <Input inputMode="decimal" autoComplete="off" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name={`items.${index}.unit_label`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Unit</FormLabel>
                          <FormControl>
                            <Input placeholder="бр." autoComplete="off" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name={`items.${index}.unit_price`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Unit price</FormLabel>
                          <FormControl>
                            <Input inputMode="decimal" autoComplete="off" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name={`items.${index}.vat_rate`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>VAT rate</FormLabel>
                          <FormControl>
                            <Input inputMode="decimal" autoComplete="off" {...field} />
                          </FormControl>
                          <p className="text-xs text-muted-foreground">
                            Example: <span className="font-mono">0.20</span> ({formatPercent(field.value)})
                          </p>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name={`items.${index}.category`}
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Category</FormLabel>
                          <FormControl>
                            <Input
                              placeholder="services"
                              autoComplete="off"
                              value={field.value ?? ""}
                              onChange={(e) => field.onChange(e.target.value || null)}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="mt-7"
                    onClick={() => fieldArray.remove(index)}
                    disabled={fieldArray.fields.length <= 1}
                    aria-label="Remove item"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Notes</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Optional notes shown on the invoice"
                  className="min-h-[96px]"
                  value={field.value ?? ""}
                  onChange={(e) => field.onChange(e.target.value || null)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-4 rounded-lg border p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <h3 className="text-sm font-medium">Bulgarian invoice layout</h3>
            <p className="text-xs text-muted-foreground">
              Optional fields rendered in the Bulgarian invoice PDF.
            </p>
          </div>

          <FormField
            control={form.control}
            name="bank_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Bank name</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Bank name"
                    autoComplete="off"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="bank_bic"
            render={({ field }) => (
              <FormItem>
                <FormLabel>BIC</FormLabel>
                <FormControl>
                  <Input
                    placeholder="BIC"
                    autoComplete="off"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="bank_iban"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>IBAN</FormLabel>
                <FormControl>
                  <Input
                    placeholder="BG..."
                    autoComplete="off"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="recipient_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Recipient signer</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Received by"
                    autoComplete="name"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="compiler_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Compiler</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Prepared by"
                    autoComplete="name"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="original_label"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Original label</FormLabel>
                <FormControl>
                  <Input autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="vat_reason"
            render={({ field }) => (
              <FormItem className="sm:col-span-2">
                <FormLabel>VAT non-charge reason</FormLabel>
                <FormControl>
                  <Textarea
                    placeholder="Optional reason for not charging VAT"
                    className="min-h-[72px]"
                    value={field.value ?? ""}
                    onChange={(e) => field.onChange(e.target.value || null)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="rounded-lg border bg-muted/30 p-4">
          <div className="grid gap-2 text-sm sm:grid-cols-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground">Subtotal</span>
              <span className="font-medium">{formatCurrency(preview.subtotal, form.getValues("currency"))}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground">VAT</span>
              <span className="font-medium">{formatCurrency(preview.vatTotal, form.getValues("currency"))}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground">Total</span>
              <span className="font-medium">{formatCurrency(preview.total, form.getValues("currency"))}</span>
            </div>
          </div>
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
              disabled={createInvoice.isPending}
            >
              Cancel
            </Button>
          ) : null}
          <Button type="submit" disabled={createInvoice.isPending}>
            {createInvoice.isPending ? "Creating…" : "Create invoice"}
          </Button>
        </div>
      </form>
    </Form>
  );
}

