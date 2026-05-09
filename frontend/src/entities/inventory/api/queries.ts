import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/shared/api/client";

import {
  inventoryKeys,
  type ImportPreviewListParams,
  type InventoryItemListParams,
  type InventorySearchParams,
  type StockLevelParams,
  type StockMovementListParams,
} from "../model/query-keys";
import type {
  InventoryImportPreview,
  InventoryImportPreviewListResponse,
  InventoryItem,
  InventoryItemListResponse,
  InventoryLocationListResponse,
  InventorySearchResponse,
  StockLevelListResponse,
  StockMovementListResponse,
} from "../model/types";

const DEFAULT_ITEM_LIST_PARAMS: InventoryItemListParams = {
  company_id: "",
  limit: 50,
  offset: 0,
};

const DEFAULT_MOVEMENT_LIST_PARAMS: StockMovementListParams = {
  company_id: "",
  limit: 50,
  offset: 0,
};

const DEFAULT_LEVEL_PARAMS: StockLevelParams = { company_id: "" };

const DEFAULT_IMPORT_PREVIEW_LIST_PARAMS: ImportPreviewListParams = {
  company_id: "",
  limit: 20,
  offset: 0,
};

const DEFAULT_INVENTORY_SEARCH_LIMIT = 20;
const DEFAULT_INVENTORY_SEARCH_MIN_CONFIDENCE = 0.5;

interface InventorySearchQueryOptions {
  enabled?: boolean;
}

export function useInventoryItems(
  token?: string | null,
  params: InventoryItemListParams = DEFAULT_ITEM_LIST_PARAMS,
) {
  return useQuery({
    queryKey: inventoryKeys.items.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () => apiClient.get<InventoryItemListResponse>("/inventory/items", { token, params }),
  });
}

export function useInventoryItem(itemId: string, companyId: string, token?: string | null) {
  return useQuery({
    queryKey: inventoryKeys.items.detail(itemId, companyId),
    enabled: Boolean(token && itemId && companyId),
    queryFn: () =>
      apiClient.get<InventoryItem>(`/inventory/items/${itemId}`, {
        token,
        params: { company_id: companyId },
      }),
  });
}

export function useInventoryLocations(companyId: string, token?: string | null) {
  return useQuery({
    queryKey: inventoryKeys.locations.list({ company_id: companyId }),
    enabled: Boolean(token && companyId),
    queryFn: () =>
      apiClient.get<InventoryLocationListResponse>("/inventory/locations", {
        token,
        params: { company_id: companyId },
      }),
  });
}

export function useStockMovements(
  token?: string | null,
  params: StockMovementListParams = DEFAULT_MOVEMENT_LIST_PARAMS,
) {
  return useQuery({
    queryKey: inventoryKeys.movements.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () => apiClient.get<StockMovementListResponse>("/inventory/movements", { token, params }),
  });
}

export function useStockLevels(
  token?: string | null,
  params: StockLevelParams = DEFAULT_LEVEL_PARAMS,
) {
  return useQuery({
    queryKey: inventoryKeys.levels.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () => apiClient.get<StockLevelListResponse>("/inventory/levels", { token, params }),
  });
}

export function useImportPreviews(
  token?: string | null,
  params: ImportPreviewListParams = DEFAULT_IMPORT_PREVIEW_LIST_PARAMS,
) {
  return useQuery({
    queryKey: inventoryKeys.importPreviews.list(params),
    enabled: Boolean(token && params.company_id),
    queryFn: () =>
      apiClient.get<InventoryImportPreviewListResponse>("/inventory/import-previews", { token, params }),
  });
}

export function useImportPreview(previewId: string, token?: string | null) {
  return useQuery({
    queryKey: inventoryKeys.importPreviews.detail(previewId),
    enabled: Boolean(token && previewId),
    queryFn: () =>
      apiClient.get<InventoryImportPreview>(`/inventory/import-previews/${previewId}`, { token }),
  });
}

export function useInventorySearch(
  token: string | null | undefined,
  params: InventorySearchParams,
  options: InventorySearchQueryOptions = {},
) {
  const hasSearchContext = Boolean(token && params.company_id && params.query.trim().length >= 2);

  return useQuery({
    queryKey: inventoryKeys.search(params),
    enabled: (options.enabled ?? true) && hasSearchContext,
    staleTime: 0,
    queryFn: () =>
      apiClient.post<InventorySearchResponse>(
        "/inventory/search",
        {
          company_id: params.company_id,
          query: params.query,
          include_stock: params.include_stock ?? true,
          min_confidence: params.min_confidence ?? DEFAULT_INVENTORY_SEARCH_MIN_CONFIDENCE,
          limit: params.limit ?? DEFAULT_INVENTORY_SEARCH_LIMIT,
        },
        { token },
      ),
  });
}

