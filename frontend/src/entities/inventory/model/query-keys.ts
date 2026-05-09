import type { ImportPreviewStatus, MovementType } from "./types";

type QueryParamValue = string | number | boolean | null | undefined;

export interface InventoryItemListParams {
  [key: string]: QueryParamValue;
  company_id: string;
  category?: string;
  is_active?: boolean;
  sku?: string;
  barcode?: string;
  limit?: number;
  offset?: number;
}

export interface InventoryLocationListParams {
  [key: string]: QueryParamValue;
  company_id: string;
  limit?: number;
  offset?: number;
}

export interface StockMovementListParams {
  [key: string]: QueryParamValue;
  company_id: string;
  item_id?: string;
  location_id?: string;
  movement_type?: MovementType;
  limit?: number;
  offset?: number;
}

export interface StockLevelParams {
  [key: string]: QueryParamValue;
  company_id: string;
  item_id?: string;
  location_id?: string;
  below_reorder_point?: boolean;
}

export interface ImportPreviewListParams {
  [key: string]: QueryParamValue;
  company_id: string;
  preview_status?: ImportPreviewStatus;
  limit?: number;
  offset?: number;
}

export interface InventorySearchParams {
  [key: string]: QueryParamValue;
  company_id: string;
  query: string;
  include_stock?: boolean;
  min_confidence?: number;
  limit?: number;
}

export const inventoryKeys = {
  all: ["inventory"] as const,

  items: {
    all: [...(["inventory"] as const), "items"] as const,
    list: (params: InventoryItemListParams) => [...inventoryKeys.all, "items", "list", params] as const,
    detail: (itemId: string, companyId?: string) =>
      [...inventoryKeys.all, "items", "detail", itemId, companyId] as const,
  },

  locations: {
    all: [...(["inventory"] as const), "locations"] as const,
    list: (params: InventoryLocationListParams) =>
      [...inventoryKeys.all, "locations", "list", params] as const,
    detail: (locationId: string, companyId?: string) =>
      [...inventoryKeys.all, "locations", "detail", locationId, companyId] as const,
  },

  movements: {
    all: [...(["inventory"] as const), "movements"] as const,
    list: (params: StockMovementListParams) =>
      [...inventoryKeys.all, "movements", "list", params] as const,
  },

  levels: {
    all: [...(["inventory"] as const), "levels"] as const,
    list: (params: StockLevelParams) => [...inventoryKeys.all, "levels", "list", params] as const,
  },

  search: (params: InventorySearchParams) => [...inventoryKeys.all, "search", params] as const,

  importPreviews: {
    all: [...(["inventory"] as const), "import-previews"] as const,
    list: (params: ImportPreviewListParams) =>
      [...inventoryKeys.all, "import-previews", "list", params] as const,
    detail: (previewId: string) => [...inventoryKeys.all, "import-previews", "detail", previewId] as const,
  },
};

