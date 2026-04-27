from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, model_validator

DateOperation = Literal["current_date", "add_days", "add_months", "first_day_next_month"]


class DateToolArgs(BaseModel):
    operation: DateOperation = Field(
        default="current_date",
        description="Date operation to perform.",
    )
    base_date: date | None = Field(
        default=None,
        description="Base date in YYYY-MM-DD format. Defaults to today in UTC.",
    )
    days: int | None = Field(
        default=None,
        ge=-3660,
        le=3660,
        description="Number of days to add. Required for add_days.",
    )
    months: int | None = Field(
        default=None,
        ge=-120,
        le=120,
        description="Number of months to add. Required for add_months.",
    )

    @model_validator(mode="after")
    def validate_operation_inputs(self):
        if self.operation == "add_days" and self.days is None:
            raise ValueError("days is required for add_days")
        if self.operation == "add_months" and self.months is None:
            raise ValueError("months is required for add_months")
        return self


def _today() -> date:
    return datetime.now(UTC).date()


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def date_helper(**kwargs) -> str:
    """Return today's date or calculate common invoice dates in YYYY-MM-DD format."""
    args = DateToolArgs.model_validate(kwargs)
    base_date = args.base_date or _today()

    if args.operation == "current_date":
        result = base_date
    elif args.operation == "add_days":
        result = base_date + timedelta(days=args.days or 0)
    elif args.operation == "add_months":
        result = _add_months(base_date, args.months or 0)
    else:
        result = _add_months(base_date.replace(day=1), 1)

    return result.isoformat()


date_tool = StructuredTool.from_function(
    func=date_helper,
    name="date_helper",
    description=(
        "Get today's date and calculate invoice dates. Use this for relative dates "
        "such as today, tomorrow, in 14 days, next month, or first day of next month."
    ),
    args_schema=DateToolArgs,
)
