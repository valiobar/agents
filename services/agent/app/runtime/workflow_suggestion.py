from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

WORKFLOW_SALES_INVOICE_INVENTORY: Literal["sales_invoice_inventory"] = "sales_invoice_inventory"
WORKFLOW_SUGGESTION_CONFIDENCE_THRESHOLD = 0.85

_INVOICE_KEYWORDS = re.compile(
    r"\b(invoic(?:e|ing)|bill(?:ing)?|faktur[ae]?|sales\s+order|фактур\w*)\b",
    re.IGNORECASE,
)
_CREATE_INVOICE_INTENT_KEYWORDS = re.compile(
    r"\b("
    r"create|make|issue|prepare|generate|send|draft|"
    r"направ\w*|създа\w*|изда\w*|пусн\w*|подготв\w*|генерира\w*"
    r")\b",
    re.IGNORECASE,
)
_PARTNER_TO_PATTERN = re.compile(
    r"\b(?:to|към|на)\s+(.{1,80})",
    re.IGNORECASE,
)
_PARTNER_FOR_PATTERN = re.compile(
    r"\bfor\s+(.{1,80})",
    re.IGNORECASE,
)
_PARTNER_STOP_PATTERN = re.compile(
    r"\s+(?:with|for|invoice|bill|stock|sku|за|със?|от)\b",
    re.IGNORECASE,
)
_LINE_PATTERN = re.compile(
    r"(?:(\d+(?:[.,]\d+)?)\s*[x×]\s*(\w[\w ._-]{1,80})|"
    r"(\w[\w ._-]{1,80})\s*[x×]\s*(\d+(?:[.,]\d+)?))",
    re.IGNORECASE,
)
_NATURAL_QUANTITY_LINE_PATTERN = re.compile(
    r"\b(?:for|за|with|със?)\s+(\d+(?:[.,]\d+)?)\s+(.{1,80})",
    re.IGNORECASE,
)
_LINE_STOP_PATTERN = re.compile(r"\s+(?:to|към|на)\b", re.IGNORECASE)


class SalesInvoiceWorkflowPrefill(TypedDict, total=False):
    partner_query: str | None
    currency: str | None
    lines: list[dict[str, Any]]


class WorkflowSuggestion(TypedDict, total=False):
    workflow: str
    confidence: float
    reason: str
    prefill: dict[str, Any]


class SalesInvoiceWorkflowSuggestion(WorkflowSuggestion):
    workflow: Literal["sales_invoice_inventory"]
    confidence: float
    reason: str
    prefill: SalesInvoiceWorkflowPrefill


def message_mentions_stock_backed_invoice(message: str) -> bool:
    normalized = message.strip()
    if not normalized:
        return False
    mentions_invoice = bool(_INVOICE_KEYWORDS.search(normalized))
    if not mentions_invoice:
        return False
    return bool(
        _CREATE_INVOICE_INTENT_KEYWORDS.search(normalized)
        or _LINE_PATTERN.search(normalized)
        or _NATURAL_QUANTITY_LINE_PATTERN.search(normalized)
    )


def _append_line(lines: list[dict[str, Any]], *, quantity: str, query: str) -> None:
    normalized_quantity = quantity.replace(",", ".")
    normalized_query = query.strip()
    if not normalized_query:
        return
    if any(
        line.get("quantity") == normalized_quantity and line.get("query") == normalized_query
        for line in lines
    ):
        return
    lines.append(
        {
            "description": normalized_query[:500],
            "query": normalized_query[:500],
            "quantity": normalized_quantity,
        }
    )


def _strip_at_stop_pattern(value: str, pattern: re.Pattern[str]) -> str:
    return pattern.split(value, maxsplit=1)[0].strip(" .,'")


def infer_sales_invoice_prefill(message: str) -> SalesInvoiceWorkflowPrefill:
    partner_query: str | None = None
    partner_match = _PARTNER_TO_PATTERN.search(message) or _PARTNER_FOR_PATTERN.search(message)
    if partner_match:
        candidate = _strip_at_stop_pattern(partner_match.group(1), _PARTNER_STOP_PATTERN)
        if candidate:
            partner_query = candidate[:200]

    lines: list[dict[str, Any]] = []
    for match in _LINE_PATTERN.finditer(message):
        if match.group(1) and match.group(2):
            _append_line(lines, quantity=match.group(1), query=match.group(2))
        else:
            _append_line(lines, quantity=match.group(4), query=match.group(3))

    for match in _NATURAL_QUANTITY_LINE_PATTERN.finditer(message):
        query = _strip_at_stop_pattern(match.group(2), _LINE_STOP_PATTERN)
        _append_line(lines, quantity=match.group(1), query=query)

    prefill: SalesInvoiceWorkflowPrefill = {"lines": lines}
    if partner_query:
        prefill["partner_query"] = partner_query
    return prefill


def build_sales_invoice_workflow_suggestion(
    *,
    confidence: float,
    reason: str,
    prefill: SalesInvoiceWorkflowPrefill | None,
) -> SalesInvoiceWorkflowSuggestion | None:
    if confidence < WORKFLOW_SUGGESTION_CONFIDENCE_THRESHOLD:
        return None
    if prefill is None:
        return None

    return {
        "workflow": WORKFLOW_SALES_INVOICE_INVENTORY,
        "confidence": confidence,
        "reason": reason,
        "prefill": prefill,
    }
