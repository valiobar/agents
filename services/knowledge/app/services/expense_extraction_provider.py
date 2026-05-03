from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Protocol

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.errors import ExpenseExtractionFailedError
from app.models.expense_extraction import ExpenseDraft, ExpenseDraftRequestSourceDocumentType

logger = logging.getLogger(__name__)


class ExpenseExtractionProvider(Protocol):
    async def extract_draft(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        extracted_text: str | None,
        source_document_type: ExpenseDraftRequestSourceDocumentType,
        source_document_id: str,
    ) -> ExpenseDraft: ...


def _normalize_content_type(content_type: str) -> str:
    ct = (content_type or "").lower().strip()
    if ct == "image/jpg":
        return "image/jpeg"
    return ct


def _build_openai_upload_part(*, filename: str, content_type: str, content: bytes) -> dict[str, Any]:
    """
    Build a Responses API content part for either image bytes or file bytes.

    We prefer `input_image` for common image types and fall back to `input_file`
    for everything else (e.g. scanned PDFs).
    """
    normalized = _normalize_content_type(content_type)
    b64 = base64.b64encode(content).decode("ascii")

    if normalized in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        return {
            "type": "input_image",
            "image_url": f"data:{normalized};base64,{b64}",
        }

    if normalized.startswith("image/"):
        raise RuntimeError(
            f"Unsupported receipt image type '{content_type}'. "
            "Please upload a PNG, JPEG, WEBP, or GIF image."
        )

    return {
        "type": "input_file",
        "filename": filename or "upload",
        "file_data": f"data:{normalized or 'application/octet-stream'};base64,{b64}",
    }


def _build_extraction_prompt(
    *,
    source_document_type: ExpenseDraftRequestSourceDocumentType,
    extracted_text: str | None,
) -> str:
    return (
        "You are an expense data extraction system.\n"
        "Return a single JSON object that strictly matches the `ExpenseDraft` schema.\n"
        "\n"
        "Rules:\n"
        "- Return valid JSON only. Do not include markdown, comments, trailing commas, or unquoted values.\n"
        "- Use `confidence` in [0, 1].\n"
        "- Add human-readable strings to `warnings` when you infer or default values.\n"
        "- Always set `counterparty` to the vendor, merchant, supplier, or payee name. "
        "If no name is visible, set it to \"Unknown counterparty\" and add a warning.\n"
        "- If the document number is visible (invoice/receipt number, reference, etc.), set `source_document_number`.\n"
        "- Quote every identifier-like value as a string, including document numbers, registration numbers, VAT numbers, SKU values, and barcodes. Preserve leading zeros.\n"
        "- Quote every decimal amount, quantity, unit price, VAT rate, and deductible rate as a string, for example \"24.01\", \"1\", \"0.20\", or \"1.0\".\n"
        "- Classify `source_document_type` as either 'invoice' or 'receipt'. Use invoice for supplier invoices/bills that identify a vendor and invoice number; use receipt for point-of-sale receipts or simple payment confirmations.\n"
        "- If the source document type below is invoice or receipt, use that explicit type. If it is auto, infer the type from the document.\n"
        "- For invoices, populate `vendor_partner` with supplier details when visible. Use null for unknown optional fields and add warnings for missing required supplier details.\n"
        "- For receipts, set `vendor_partner` to null.\n"
        "- If line items are visible (SKU, barcode, VAT rate, unit, quantities), populate `items`.\n"
        "- If the expense date is missing, infer it if possible; otherwise set it to today's date and warn.\n"
        "- If category is ambiguous, set category='other' and warn.\n"
        "- If currency is unclear, default to EUR and warn.\n"
        "- If total amount is missing but items exist, leave `amount` null and warn.\n"
        "- Return all rate fields as quoted fractions from 0 to 1: 20% must be \"0.20\", 100% must be \"1.0\".\n"
        "\n"
        f"Source document type: {source_document_type}\n"
        "\n"
        "Extracted text (may be empty or partial):\n"
        f"{extracted_text or ''}\n"
    )


def _make_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively transform a Pydantic JSON schema so it satisfies OpenAI's
    strict structured-output requirements: every object must set
    ``additionalProperties: false`` and list all fields in ``required``.
    ``$defs`` are resolved in-place.

    Note: The ``strict`` flag itself belongs in the format envelope
    (``text.format.strict``), not inside the schema body, so we deliberately
    do not add it here.
    """
    schema = schema.copy()

    if "$defs" in schema:
        for defn in schema["$defs"].values():
            _make_strict_schema_node(defn)

    _make_strict_schema_node(schema)
    return schema


def _make_strict_schema_node(node: dict[str, Any]) -> None:
    if node.get("type") == "object":
        node["additionalProperties"] = False
        props = node.get("properties", {})
        node["required"] = list(props.keys())
        for prop in props.values():
            _make_strict_schema_node(prop)

    if "anyOf" in node:
        for variant in node["anyOf"]:
            if isinstance(variant, dict):
                _make_strict_schema_node(variant)

    if node.get("type") == "array" and isinstance(node.get("items"), dict):
        _make_strict_schema_node(node["items"])


def _sanitize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Truncate or null-out fields the model may hallucinate garbage into."""
    field_limits = {
        "description": 500,
        "unit_label": 32,
        "sku": 120,
        "barcode": 120,
    }
    for field, limit in field_limits.items():
        if field in item and isinstance(item[field], str) and len(item[field]) > limit:
            logger.warning("Truncating item field %s (%d chars)", field, len(item[field]))
            item[field] = item[field][:limit]
    return item


def _sanitize_draft(data: dict[str, Any]) -> dict[str, Any]:
    """Best-effort cleanup of raw LLM JSON before Pydantic validation."""
    counterparty = data.get("counterparty")
    if not isinstance(counterparty, str) or not counterparty.strip():
        vendor_partner = data.get("vendor_partner")
        vendor_name = vendor_partner.get("name") if isinstance(vendor_partner, dict) else None
        data["counterparty"] = (
            vendor_name.strip()
            if isinstance(vendor_name, str) and vendor_name.strip()
            else "Unknown counterparty"
        )
        warnings = data.get("warnings")
        if not isinstance(warnings, list):
            warnings = []
        warnings.append("Counterparty was missing and was inferred or defaulted.")
        data["warnings"] = warnings

    if isinstance(data.get("items"), list):
        data["items"] = [_sanitize_item(it) for it in data["items"] if isinstance(it, dict)]
    return data


def _parse_first_json_object(raw_text: str) -> dict[str, Any]:
    """
    Parse the first JSON object from model output.

    OpenAI's structured output occasionally appends trailing braces or text
    (we have observed `} }` suffixes from `gpt-4.1-mini`). ``json.loads`` and
    Pydantic's strict ``model_validate_json`` both reject any trailing data,
    so we use ``raw_decode`` to read just the first object and discard the
    rest.
    """
    text = raw_text.strip()
    if not text:
        raise RuntimeError("Expense extraction provider returned empty output")

    decoder = json.JSONDecoder()

    first_brace = text.find("{")
    if first_brace == -1:
        raise RuntimeError("Expense extraction provider output did not contain a JSON object")
    if first_brace > 0:
        text = text[first_brace:]

    try:
        data, end_index = decoder.raw_decode(text)
    except json.JSONDecodeError as exc:
        snippet = text[:200].replace("\n", " ")
        logger.error("Expense extraction JSON decode failed at col %d: %s", exc.colno, snippet)
        raise RuntimeError(
            f"Expense extraction provider returned malformed JSON: {exc.msg} (col {exc.colno})"
        ) from exc

    trailing = text[end_index:].strip()
    if trailing:
        logger.info(
            "Discarding trailing model output after JSON object (%d chars)", len(trailing)
        )

    if not isinstance(data, dict):
        raise RuntimeError("Expense extraction provider returned non-object JSON payload")
    return data


class OpenAIExpenseExtractionProvider:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for expense extraction")
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self.model = model

    async def extract_draft(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        extracted_text: str | None,
        source_document_type: ExpenseDraftRequestSourceDocumentType,
        source_document_id: str,
    ) -> ExpenseDraft:
        prompt = _build_extraction_prompt(
            source_document_type=source_document_type,
            extracted_text=extracted_text,
        )

        parts: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        if extracted_text is None:
            parts.append(
                _build_openai_upload_part(
                    filename=filename,
                    content_type=content_type,
                    content=content,
                )
            )

        schema = _make_strict_schema(ExpenseDraft.model_json_schema())

        started = time.monotonic()
        logger.info(
            "Calling OpenAI Responses API for expense extraction (model=%s, content_type=%s, "
            "has_text=%s, content_bytes=%d)",
            self.model,
            content_type,
            extracted_text is not None,
            len(content),
        )
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": parts}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "ExpenseDraft",
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
        except Exception:
            logger.exception(
                "OpenAI Responses API call failed after %.1fs", time.monotonic() - started
            )
            raise

        elapsed = time.monotonic() - started
        raw_text = response.output_text
        if not raw_text:
            logger.error("OpenAI returned empty output after %.1fs", elapsed)
            raise RuntimeError("Expense extraction provider returned empty output")

        logger.info(
            "OpenAI extraction completed in %.1fs (output_chars=%d)", elapsed, len(raw_text)
        )

        # OpenAI's strict structured output usually returns valid JSON, but
        # `gpt-4.1-mini` occasionally appends extra characters (e.g. `} }`).
        # Use the tolerant parser as the primary path so we don't error out
        # on a single trailing brace.
        data = _parse_first_json_object(raw_text)
        data = _sanitize_draft(data)
        try:
            draft = ExpenseDraft.model_validate(data)
        except ValidationError as exc:
            logger.error("Expense draft schema validation failed: %s", exc)
            raise ExpenseExtractionFailedError(
                "Expense extraction returned an invalid draft. Please try another image or enter the expense manually."
            ) from exc

        return draft.model_copy(update={"source_document_id": source_document_id})
