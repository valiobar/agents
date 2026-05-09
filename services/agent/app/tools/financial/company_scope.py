from __future__ import annotations

from collections.abc import Awaitable, Callable


def _company_scope_required(action: str) -> str:
    return (
        f"Choose a company before {action}. "
        "Use list_companies or resolve_company_by_name, then call this tool with company_id."
    )


def _scoped_company_id(
    assigned_company_id: str | None,
    requested_company_id: str | None,
    action: str,
) -> tuple[str | None, str | None]:
    if assigned_company_id is None:
        return requested_company_id, None
    if requested_company_id is not None and requested_company_id != assigned_company_id:
        return (
            None,
            f"This agent is scoped to one company and cannot use company_id '{requested_company_id}' for {action}. "
            "Retry without company_id so the agent uses its assigned company.",
        )
    return assigned_company_id, None


async def _with_scoped_company(
    assigned_company_id: str | None,
    requested_company_id: str | None,
    action: str,
    callback: Callable[[str], Awaitable[str]],
) -> str:
    target_company_id, scope_error = _scoped_company_id(assigned_company_id, requested_company_id, action)
    if scope_error:
        return scope_error
    if target_company_id is None:
        return _company_scope_required(action)
    return await callback(target_company_id)


def scoped_company_id(
    assigned_company_id: str | None,
    requested_company_id: str | None,
    action: str,
) -> tuple[str | None, str | None]:
    return _scoped_company_id(assigned_company_id, requested_company_id, action)


async def with_scoped_company(
    assigned_company_id: str | None,
    requested_company_id: str | None,
    action: str,
    callback: Callable[[str], Awaitable[str]],
) -> str:
    return await _with_scoped_company(assigned_company_id, requested_company_id, action, callback)
