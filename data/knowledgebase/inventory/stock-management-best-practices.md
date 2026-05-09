# Stock Management Best Practices

## Reorder Point Formula

Use reorder point (ROP) to trigger replenishment before stockouts:

ROP = (Average Daily Usage x Lead Time in Days) + Safety Stock

Example:
- Average daily usage: 12 units
- Lead time: 8 days
- Safety stock: 40 units
- ROP = (12 x 8) + 40 = 136 units

When available stock is at or below 136, place a purchase order.

## Safety Stock Baseline

For a practical baseline when detailed variance data is unavailable:

Safety Stock = (Max Daily Usage x Max Lead Time) - (Average Daily Usage x Average Lead Time)

Review this monthly for high-turnover SKUs and quarterly for slow movers.

## Target Stock Level

Target stock level should cover normal demand plus a short replenishment buffer:

Target Stock = (Average Daily Usage x (Lead Time + Review Period)) + Safety Stock

Use this to suggest reorder quantity:

Suggested Reorder Qty = max(Target Stock - Current Available, 0)

## ABC Analysis Overview

Segment items by value contribution to focus control effort:

- A items: top 70-80% of annual consumption value, usually 10-20% of items
- B items: next 15-25% of value
- C items: remaining low-value tail

Recommended policy:
- A: tight review cadence, strict cycle counts, lower tolerance for stockouts
- B: balanced controls and monthly checks
- C: simplified controls and larger order batches

## Operational Guardrails

- Define movement reasons for every adjustment.
- Avoid negative stock unless explicitly allowed by policy.
- Run weekly low-stock review and escalate A-item shortages.
- Reconcile physical counts against system stock by location.
