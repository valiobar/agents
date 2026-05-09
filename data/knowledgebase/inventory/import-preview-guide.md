# Supplier Invoice Import Preview Guide

## Goal

Import previews let users inspect parsed supplier invoice lines before writing inventory items and stock movements. This reduces accidental item creation and wrong quantities.

## Typical Workflow

1. Upload or trigger supplier invoice import.
2. Open preview and review extracted header data and line items.
3. Check line-level matching:
   - exact match to existing inventory item
   - probable match requiring confirmation
   - no match (new item candidate)
4. Resolve warnings.
5. Confirm import only after user approval.

## Common Warning Types

- Missing required fields (name, quantity, or unit).
- Quantity or unit parse ambiguity (for example comma vs dot decimal formats).
- Duplicate candidate matches for one source line.
- Price mismatch versus last known purchase cost.
- Unknown tax/VAT text that cannot be normalized.

## Resolution Guidelines

- Prefer explicit user confirmation when confidence is medium/low.
- For unmatched lines, create a draft item suggestion with normalized name and unit.
- Keep imported quantities in base units used by stock movements.
- Preserve source line references to support post-import audit.

## Confirm vs Cancel

- Confirm preview:
  - creates new inventory items when needed
  - updates known item purchase metadata when configured
  - records receipt stock movements
- Cancel preview:
  - marks preview cancelled
  - creates no items and no stock movements

## Operator Checklist

- Verify company and location scope.
- Verify critical A-items first.
- Confirm quantities and units for all lines.
- Confirm warnings are resolved or explicitly accepted.
- Ask for final user confirmation before applying.
