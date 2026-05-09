export type MovementType =
  | "receipt"
  | "issue"
  | "adjustment"
  | "transfer_in"
  | "transfer_out"
  | "return";

export type ImportPreviewStatus = "draft" | "confirmed" | "cancelled";

export type ImportSourceType = "supplier_invoice_upload" | "agent";

export type SearchMatchReason = "sku" | "barcode" | "alias" | "text" | "prefix";

export interface InventoryItem {
  id: string;
  user_id: string;
  created_by_user_id: string;
  updated_by_user_id: string;
  company_id: string;
  sku: string;
  name: string;
  description: string | null;
  category: string | null;
  barcode: string | null;
  aliases: string[];
  search_text: string;
  unit: string;
  selling_price: string | null;
  reorder_point: string | null;
  target_stock_level: string | null;
  supplier_partner_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryLocation {
  id: string;
  user_id: string;
  company_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockMovement {
  id: string;
  user_id: string;
  performed_by_user_id: string;
  company_id: string;
  item_id: string;
  location_id: string;
  movement_type: MovementType;
  quantity_delta: string;
  reason: string | null;
  source_type: string | null;
  source_id: string | null;
  source_line_id: string | null;
  occurred_at: string;
  created_at: string;
}

export interface StockLevel {
  item_id: string;
  item_name: string;
  item_sku: string;
  location_id: string;
  location_name: string;
  available_quantity: string;
  unit: string;
}

export interface InventorySearchMatch {
  item_id: string;
  name: string;
  description: string | null;
  sku: string | null;
  category: string | null;
  unit: string;
  selling_price: string | null;
  confidence: number;
  match_reason: SearchMatchReason;
  available_quantity: string | null;
}

export interface InventorySearchResponse {
  matches: InventorySearchMatch[];
  total_available_quantity: string | null;
}

export interface ListMetadata {
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  truncated: boolean;
  next_offset: number | null;
}

export interface InventoryItemListResponse extends ListMetadata {
  items: InventoryItem[];
}

export interface InventoryLocationListResponse extends ListMetadata {
  locations: InventoryLocation[];
}

export interface StockMovementListResponse extends ListMetadata {
  movements: StockMovement[];
}

export interface InventoryImportPreviewListResponse extends ListMetadata {
  previews: InventoryImportPreview[];
}

export interface StockLevelListResponse {
  total_stock_level_count: number;
  unique_item_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  truncated: boolean;
  next_offset: number | null;
  levels: StockLevel[];
}

export interface SupplierInvoiceLineCandidate {
  description: string;
  sku: string | null;
  barcode: string | null;
  quantity: string;
  unit: string | null;
  unit_price: string | null;
}

export interface ImportPreviewLine {
  candidate: SupplierInvoiceLineCandidate;
  matched_item_id: string | null;
  proposed_item: InventoryItemCreate | null;
  location_id: string;
  receipt_quantity: string;
  warnings: string[];
}

export interface InventoryImportPreview {
  id: string;
  user_id: string;
  company_id: string;
  document_id: string | null;
  source_type: ImportSourceType;
  status: ImportPreviewStatus;
  lines: ImportPreviewLine[];
  created_at: string;
  updated_at: string;
}

export interface InventoryImportResult {
  preview_id: string;
  items_created: number;
  items_updated: number;
  movements_created: number;
}

export interface InventoryItemCreate {
  company_id: string;
  sku: string;
  name: string;
  description?: string | null;
  category?: string | null;
  barcode?: string | null;
  aliases?: string[];
  unit: string;
  selling_price?: string | null;
  reorder_point?: string | null;
  target_stock_level?: string | null;
  supplier_partner_id?: string | null;
  is_active?: boolean;
}

