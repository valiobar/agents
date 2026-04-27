"use client";

import { Download } from "lucide-react";
import { pdf } from "@react-pdf/renderer";
import { useState } from "react";

import type { Invoice } from "@/entities/invoice/model/types";
import { Button } from "@/shared/ui/button";

import { InvoicePdfDocument } from "../model/invoice-pdf-document";

function buildInvoicePdfFilename(invoiceNumber: string) {
  const safeInvoiceNumber = invoiceNumber.trim().replaceAll(/[^a-zA-Z0-9._-]+/g, "-") || "invoice";
  return `faktura-${safeInvoiceNumber}.pdf`;
}

export function DownloadInvoicePdfButton({ invoice }: Readonly<{ invoice: Invoice }>) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canGenerate = Boolean(invoice.supplier_snapshot && invoice.recipient_snapshot);
  const disabledReason =
    canGenerate === true
      ? null
      : "PDF е наличен само за фактури със snapshot данни (доставчик/получател). Нужно е backfill или нова фактура.";

  async function handleDownload() {
    if (!canGenerate) return;
    setIsGenerating(true);
    setError(null);

    try {
      const blob = await pdf(<InvoicePdfDocument invoice={invoice} />).toBlob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = buildInvoicePdfFilename(invoice.invoice_number);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError("Unable to generate PDF. Please try again.");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div className="space-y-2">
      <div title={disabledReason ?? undefined}>
        <Button type="button" onClick={handleDownload} disabled={isGenerating || !canGenerate}>
          <Download className="mr-2 h-4 w-4" />
          {isGenerating ? "Генериране на PDF..." : "Изтегли PDF"}
        </Button>
      </div>
      {canGenerate === false ? <p className="text-sm text-muted-foreground">{disabledReason}</p> : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
