"use client";

import { Badge } from "@/shared/ui/badge";

import type { InventoryItem } from "../model/types";

interface InventoryItemRowProps {
  item: InventoryItem;
  availableQuantity?: string;
  onClick?: () => void;
}

export function InventoryItemRow({
  item,
  availableQuantity,
  onClick,
}: Readonly<InventoryItemRowProps>) {
  return (
    <tr
      className="cursor-pointer border-b transition-colors hover:bg-muted/50"
      onClick={onClick}
    >
      <td className="px-4 py-3 font-mono text-sm">{item.sku}</td>
      <td className="px-4 py-3">{item.name}</td>
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {item.category ?? "ù"}
      </td>
      <td className="px-4 py-3 text-sm">{item.unit}</td>
      <td className="px-4 py-3 text-right font-mono">
        {availableQuantity ?? "ù"}
      </td>
      <td className="px-4 py-3">
        {item.is_active ? (
          <Badge variant="default">Active</Badge>
        ) : (
          <Badge variant="secondary">Inactive</Badge>
        )}
      </td>
    </tr>
  );
}

