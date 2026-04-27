from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128

_MONEY_QUANT = Decimal("0.01")
_RATE_QUANT = Decimal("0.0001")
EUR_TO_BGN_RATE = Decimal("1.95583000")
EXCHANGE_RATES_TO_BGN: dict[str, Decimal] = {
    "BGN": Decimal("1"),
    "EUR": EUR_TO_BGN_RATE,
}


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANT, rounding=ROUND_HALF_UP)


def quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(_RATE_QUANT, rounding=ROUND_HALF_UP)


def convert_to_bgn(amount: Decimal, currency: str) -> Decimal | None:
    rate = EXCHANGE_RATES_TO_BGN.get(currency)
    if rate is None:
        return None
    return quantize_money(amount * rate)


def decimal_to_bson(value: Any) -> Any:
    if isinstance(value, Decimal):
        return Decimal128(str(value))
    if isinstance(value, list):
        return [decimal_to_bson(item) for item in value]
    if isinstance(value, dict):
        return {key: decimal_to_bson(item) for key, item in value.items()}
    return value


def bson_to_decimal(value: Any) -> Any:
    if isinstance(value, Decimal128):
        return value.to_decimal()
    if isinstance(value, list):
        return [bson_to_decimal(item) for item in value]
    if isinstance(value, dict):
        return {key: bson_to_decimal(item) for key, item in value.items()}
    return value


def date_to_datetime_range(value: date, *, end_of_day: bool = False) -> datetime:
    """
    Helper for repositories that store dates as datetimes.

    - Start-of-day: 00:00:00Z
    - End-of-day:   23:59:59.999999Z
    """
    if end_of_day:
        return datetime.combine(value, time.max, tzinfo=timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def document_timestamps(doc: dict[str, Any], *, fallback_date_field: str) -> tuple[datetime, datetime]:
    created_at = doc.get("created_at")
    if not isinstance(created_at, datetime):
        object_id = doc.get("_id")
        if isinstance(object_id, ObjectId):
            created_at = object_id.generation_time
        elif isinstance(doc.get(fallback_date_field), datetime):
            created_at = doc[fallback_date_field]
        else:
            created_at = datetime.now(timezone.utc)

    updated_at = doc.get("updated_at")
    if not isinstance(updated_at, datetime):
        updated_at = created_at

    return created_at, updated_at

