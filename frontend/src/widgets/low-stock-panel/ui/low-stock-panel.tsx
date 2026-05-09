"use client";

import { AlertTriangle } from "lucide-react";
import { useSession } from "next-auth/react";

import { useStockLevels } from "@/entities/inventory/api/queries";
import { EmptyState } from "@/shared/ui/empty-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/ui/card";
import { Spinner } from "@/shared/ui/spinner";

interface LowStockPanelProps {
  companyId: string;
}

export function LowStockPanel({ companyId }: Readonly<LowStockPanelProps>) {
  const { data: session } = useSession();

  const levels = useStockLevels(session?.accessToken, {
    company_id: companyId,
    below_reorder_point: true,
  });

  if (!companyId) {
    return null;
  }

  if (levels.isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Spinner />
      </div>
    );
  }

  if (levels.isError) {
    return (
      <EmptyState
        title="Unable to load low-stock items"
        description="Please try again in a moment."
      />
    );
  }

  if (!levels.data?.levels.length) {
    return null;
  }

  return (
    <Card className="border-destructive/20">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          Low Stock ({levels.data.returned_count} items)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2">
          {levels.data.levels.map((level) => (
            <li
              key={`${level.item_id}-${level.location_id}`}
              className="flex items-center justify-between text-sm"
            >
              <div>
                <span className="font-medium">{level.item_name || level.item_sku || level.item_id}</span>
                {level.location_name ? (
                  <span className="ml-1 text-muted-foreground">@ {level.location_name}</span>
                ) : null}
              </div>
              <div className="text-right">
                <span className="font-mono text-destructive">{level.available_quantity}</span>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
