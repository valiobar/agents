"use client";

import { Package, RotateCcw, Search } from "lucide-react";
import { useSession } from "next-auth/react";
import { useEffect, useMemo, useState } from "react";

import { useCompanies } from "@/entities/company/api/queries";
import { useInventoryItems } from "@/entities/inventory/api/queries";
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
const PAGE_SIZE = 20;

export function InventoryTable() {
  const { data: session } = useSession();
  const companies = useCompanies(session?.accessToken);

  const defaultCompanyId = useMemo(() => {
    const companyList = companies.data ?? [];
    return companyList.find((company) => company.is_default)?.id ?? companyList[0]?.id ?? "";
  }, [companies.data]);

  const { search, category, isActive, setSearch, setCategory, setIsActive, resetFilters } =
    useInventoryFiltersStore();
  const [page, setPage] = useState(0);
  const normalizedSearch = search.trim();
  const offset = page * PAGE_SIZE;

  const items = useInventoryItems(session?.accessToken, {
    company_id: defaultCompanyId,
    search: normalizedSearch || undefined,
    category: category ?? undefined,
    is_active: isActive ?? undefined,
    limit: PAGE_SIZE,
    offset,
  });

  useEffect(() => {
    if (!defaultCompanyId) {
      resetFilters();
      setPage(0);
    }
  }, [defaultCompanyId, resetFilters]);

  useEffect(() => {
    setPage(0);
  }, [defaultCompanyId, category, isActive, normalizedSearch]);

  let statusValue = ALL_OPTION;
  if (isActive === true) {
    statusValue = STATUS_OPTIONS[0];
  } else if (isActive === false) {
    statusValue = STATUS_OPTIONS[1];
  }
  const visibleItems = items.data?.items ?? [];
  const totalCount = items.data?.total_count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const hasPreviousPage = page > 0;
  const hasNextPage = Boolean(items.data?.next_offset);

  if (companies.isLoading || items.isLoading) {
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

  if (items.isError) {
    return (
      <EmptyState
        title="Unable to load inventory"
        description="Please try again in a moment."
        action={
          <Button type="button" variant="outline" onClick={() => void items.refetch()}>
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

      {visibleItems.length ? (
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
              {visibleItems.map((item) => {
                const availableQuantity = item.available_in_stock ?? "0";
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

      {totalCount > 0 ? (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <p>
            Showing {offset + 1}-{Math.min(offset + visibleItems.length, totalCount)} of {totalCount} items
          </p>
          <div className="flex items-center gap-2">
            <span>
              Page {Math.min(page + 1, totalPages)} of {totalPages}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!hasPreviousPage || items.isFetching}
              onClick={() => setPage((current) => Math.max(current - 1, 0))}
            >
              Previous
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={!hasNextPage || items.isFetching}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
