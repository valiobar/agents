"use client";

import { FileUp } from "lucide-react";
import { useSession } from "next-auth/react";
import { useMemo, useState } from "react";

import { useImportPreviews } from "@/entities/inventory/api/queries";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { EmptyState } from "@/shared/ui/empty-state";
import { Spinner } from "@/shared/ui/spinner";

import { ImportPreviewActions } from "@/features/inventory-import-review/ui/import-preview-actions";

interface ImportPreviewTableProps {
  companyId: string;
}

export function ImportPreviewTable({ companyId }: Readonly<ImportPreviewTableProps>) {
  const { data: session } = useSession();
  const [expandedPreviewIds, setExpandedPreviewIds] = useState<Record<string, boolean>>({});

  const previews = useImportPreviews(session?.accessToken, {
    company_id: companyId,
    limit: 20,
    offset: 0,
  });

  const previewCountLabel = useMemo(() => previews.data?.returned_count ?? 0, [previews.data]);

  if (!companyId) {
    return null;
  }

  if (previews.isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Spinner />
      </div>
    );
  }

  if (previews.isError) {
    return (
      <EmptyState
        title="Unable to load import previews"
        description="Please try again in a moment."
      />
    );
  }

  if (!previews.data?.previews.length) {
    return null;
  }

  return (
    <section className="space-y-4">
      <h3 className="flex items-center gap-2 text-lg font-semibold">
        <FileUp className="h-5 w-5" />
        Import Previews ({previewCountLabel})
      </h3>

      {previews.data.previews.map((preview) => {
        const isExpanded = expandedPreviewIds[preview.id] ?? false;
        return (
          <Card key={preview.id}>
            <CardHeader className="flex flex-row items-center justify-between gap-3 pb-3">
              <div className="flex items-center gap-2">
                <CardTitle className="text-sm font-medium">
                  Preview {preview.id.slice(-8)}
                </CardTitle>
                <Badge variant={preview.status === "draft" ? "outline" : "secondary"}>
                  {preview.status}
                </Badge>
              </div>

              <div className="flex items-center gap-2">
                {session?.accessToken ? (
                  <ImportPreviewActions
                    previewId={preview.id}
                    status={preview.status}
                    token={session.accessToken}
                  />
                ) : null}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setExpandedPreviewIds((current) => ({
                      ...current,
                      [preview.id]: !isExpanded,
                    }))
                  }
                >
                  {isExpanded ? "Hide lines" : "Show lines"}
                </Button>
              </div>
            </CardHeader>

            {isExpanded ? (
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-muted-foreground">
                        <th className="pb-2">Description</th>
                        <th className="pb-2">SKU</th>
                        <th className="pb-2 text-right">Qty</th>
                        <th className="pb-2">Match</th>
                        <th className="pb-2">Warnings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.lines.map((line) => {
                        const lineKey = [
                          line.candidate.description,
                          line.candidate.sku ?? "",
                          line.location_id,
                          line.receipt_quantity,
                        ].join("|");
                        let matchBadge = (
                          <Badge
                            variant="outline"
                            className="border-destructive/40 text-destructive"
                          >
                            Unmatched
                          </Badge>
                        );
                        if (line.matched_item_id) {
                          matchBadge = <Badge>Matched</Badge>;
                        } else if (line.proposed_item) {
                          matchBadge = <Badge variant="outline">New item</Badge>;
                        }

                        return (
                          <tr key={lineKey} className="border-b last:border-0">
                            <td className="py-2">{line.candidate.description}</td>
                            <td className="py-2 font-mono">{line.candidate.sku ?? "-"}</td>
                            <td className="py-2 text-right font-mono">{line.receipt_quantity}</td>
                            <td className="py-2">{matchBadge}</td>
                            <td className="py-2">
                              {line.warnings.length > 0 ? (
                                <span className="text-xs text-destructive">
                                  {line.warnings.join("; ")}
                                </span>
                              ) : (
                                <span className="text-xs text-muted-foreground">None</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            ) : null}
          </Card>
        );
      })}
    </section>
  );
}
