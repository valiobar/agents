"use client";

import { Package, RotateCcw, Search } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useMemo } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { useInventoryItems, useStockLevels } from "@/entities/inventory/api/queries";
import { StockLevelBadge } from "@/entities/inventory/ui/stock-level-badge";
import { useInventoryFiltersStore } from "@/shared/store/inventory-filters-store";
import { Button } from "@/shared/ui/button";
import { EmptyState } from "@/shared/ui/empty-state";
import { Input } from "@/shared/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/ui/select";
import { Spinner } from "@/shared/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

const ALL_OPTION = "all";
const CATEGORY_OPTIONS = ["electronics", "office", "raw_materials"] as const;
const STATUS_OPTIONS = ["active", "inactive"] as const;

export function InventoryTable() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  const { search, category, isActive, setSearch, setCategory, setIsActive, resetFilters } =
    useInventoryFiltersStore();

  const items = useInventoryItems(session?.accessToken, {
    company_id: defaultCompanyId,
    category: category ?? undefined,
    is_active: isActive ?? undefined,
    limit: 50,
    offset: 0,
  });

  const levels = useStockLevels(session?.accessToken, {
    company_id: defaultCompanyId,
  });

  useEffect(() => {
    if (!defaultCompanyId) {
      resetFilters();
    }
  }, [defaultCompanyId, resetFilters]);

  const levelByItemId = useMemo(() => {
    const map = new Map<string, string>();
    for (const level of levels.data?.levels ?? []) {
      const current = Number.parseFloat(map.get(level.item_id) ?? "0");
      const next = Number.parseFloat(level.available_quantity);
      map.set(level.item_id, String(current + next));
    }
    return map;
  }, [levels.data]);

  const normalizedSearch = search.trim().toLowerCase();
  let statusValue = ALL_OPTION;
  if (isActive === true) {
    statusValue = STATUS_OPTIONS[0];
  } else if (isActive === false) {
    statusValue = STATUS_OPTIONS[1];
  }
  const filteredItems = useMemo(
    () =>
      (items.data?.items ?? []).filter((item) => {
        if (!normalizedSearch) {
          return true;
        }
        return (
          item.name.toLowerCase().includes(normalizedSearch) ||
          item.sku.toLowerCase().includes(normalizedSearch)
        );
      }),
    [items.data?.items, normalizedSearch],
  );

  if (companies.isLoading || items.isLoading || levels.isLoading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Spinner />
      </div>
    );
  }

  if (!companies.data?.length) {
    return (
      <EmptyState
        title="Create a company first"
        description="Inventory is scoped to a company. Create a company before adding items."
      />
    );
  }

  if (items.isError || levels.isError) {
    return (
      <EmptyState
        title="Unable to load inventory"
        description="Please try again in a moment."
        action={
          <Button type="button" variant="outline" onClick={() => void Promise.all([items.refetch(), levels.refetch()])}>
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <p className="mb-2 text-xs font-medium text-muted-foreground">Search</p>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="Search by name or SKU"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Category</p>
            <Select
              value={category ?? ALL_OPTION}
              onValueChange={(value) => setCategory(value === ALL_OPTION ? null : value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_OPTION}>All categories</SelectItem>
                {CATEGORY_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option.replace("_", " ")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Status</p>
            <Select
              value={statusValue}
              onValueChange={(value) => {
                if (value === ALL_OPTION) {
                  setIsActive(null);
                  return;
                }
                setIsActive(value === STATUS_OPTIONS[0]);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Any status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_OPTION}>Any status</SelectItem>
                <SelectItem value={STATUS_OPTIONS[0]}>Active</SelectItem>
                <SelectItem value={STATUS_OPTIONS[1]}>Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end">
          <Button type="button" variant="outline" onClick={resetFilters}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Reset filters
          </Button>
        </div>
      </div>

      {filteredItems.length ? (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead className="text-right">Stock</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredItems.map((item) => {
                const availableQuantity = levelByItemId.get(item.id) ?? "0";
                return (
                  <TableRow key={item.id}>
                    <TableCell className="font-mono text-sm">{item.sku}</TableCell>
                    <TableCell className="font-medium">{item.name}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {item.category ?? "-"}
                    </TableCell>
                    <TableCell className="text-sm">{item.unit}</TableCell>
                    <TableCell className="text-right">
                      <StockLevelBadge
                        available={availableQuantity}
                        reorderPoint={item.reorder_point}
                      />
                    </TableCell>
                    <TableCell>
                      <span
                        className={item.is_active ? "text-emerald-600" : "text-muted-foreground"}
                      >
                        {item.is_active ? "Active" : "Inactive"}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      ) : (
        <EmptyState
          title="No inventory items found"
          description="Try adjusting filters or create an item first."
          action={<Package className="mx-auto h-8 w-8 text-muted-foreground" />}
        />
      )}
    </div>
  );
}
