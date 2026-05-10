"use client";

import { useSession } from "next-auth/react";
import { useMemo } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { CreateInventoryItemDialog } from "@/features/create-inventory-item/ui/create-inventory-item-dialog";
import { RecordStockMovementDialog } from "@/features/record-stock-movement/ui/record-stock-movement-dialog";
import { InventoryTable } from "@/widgets/inventory-table/ui/inventory-table";

export default function InventoryPage() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);

  const companyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  if (!session?.accessToken || !companyId) {
    return (
      <section className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
        <p className="text-sm text-muted-foreground">Select a company to manage inventory.</p>
      </section>
    );
  }

  return (
    <section className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage items, track stock levels, and record movements.
          </p>
        </div>

        <div className="flex gap-2">
          <RecordStockMovementDialog companyId={companyId} token={session.accessToken} />
          <CreateInventoryItemDialog companyId={companyId} token={session.accessToken} />
        </div>
      </div>

      <InventoryTable />
    </section>
  );
}
