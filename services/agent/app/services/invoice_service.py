from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from app.models.company import CompanyInDB
from app.models.financial import (
    InvoiceCreate,
    InvoiceFilters,
    InvoiceInDB,
    InvoiceItem,
    InvoicePartySnapshot,
    InvoiceUpdate,
)
from app.repositories.financial_utils import quantize_money, quantize_rate
from app.repositories.invoice_repo import InvoiceRepository
from app.repositories.partner_repo import PartnerRepository
from app.services.company_service import CompanyService

_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"sent", "cancelled"},
    "sent": {"paid", "overdue", "cancelled"},
    "overdue": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}

_INVOICE_NOT_FOUND_DETAIL = "Invoice not found"


class InvoiceService:
    def __init__(
        self,
        repo: InvoiceRepository,
        company_service: CompanyService,
        partner_repo: PartnerRepository,
    ) -> None:
        self.repo = repo
        self.company_service = company_service
        self.partner_repo = partner_repo

    def _snapshot_company(self, company: CompanyInDB) -> InvoicePartySnapshot:
        return InvoicePartySnapshot(
            name=company.name,
            registration_number=company.registration_number,
            vat_number=company.vat_number,
            city=company.city,
            country=company.country,
            address=company.address,
            accountable_person=company.accountable_person,
            email=company.email,
            phone=company.phone,
            logo_data_url=company.logo_data_url,
        )

    async def _resolve_recipient(
        self, user_id: str, payload: InvoiceCreate
    ) -> tuple[str | None, InvoicePartySnapshot, str]:
        if payload.partner_id:
            partner = await self.partner_repo.resolve_by_company_identifier(
                user_id,
                payload.company_id,
                payload.partner_id,
            )
            if partner is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
            return partner.id, InvoicePartySnapshot.from_partner(partner), partner.name
        if payload.recipient is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="partner_id or recipient is required")
        return None, InvoicePartySnapshot.model_validate(payload.recipient), payload.recipient.name

    def _calculate_items(self, payload: InvoiceCreate) -> tuple[list[InvoiceItem], Decimal, Decimal, Decimal]:
        items: list[InvoiceItem] = []
        subtotal = Decimal("0")
        vat_total = Decimal("0")
        total = Decimal("0")

        for item in payload.items:
            line_subtotal = quantize_money(item.quantity * item.unit_price)
            line_vat = quantize_money(line_subtotal * quantize_rate(item.vat_rate))
            line_total = quantize_money(line_subtotal + line_vat)
            items.append(
                InvoiceItem(
                    **item.model_dump(),
                    subtotal=line_subtotal,
                    vat_amount=line_vat,
                    total=line_total,
                )
            )
            subtotal += line_subtotal
            vat_total += line_vat
            total += line_total

        return items, quantize_money(subtotal), quantize_money(vat_total), quantize_money(total)

    async def create_invoice(self, user_id: str, payload: InvoiceCreate) -> InvoiceInDB:
        company = await self.company_service.require_company(user_id, payload.company_id)
        partner_id, recipient_snapshot, counterparty = await self._resolve_recipient(user_id, payload)
        items, subtotal, vat_total, total = self._calculate_items(payload)
        invoice_number = await self.repo.next_invoice_number(user_id, payload.company_id, payload.issue_date.year)
        doc = payload.model_dump(exclude={"items", "recipient"}, mode="python")
        doc.update(
            {
                "user_id": user_id,
                "partner_id": partner_id,
                "invoice_number": invoice_number,
                "counterparty": counterparty,
                "supplier_snapshot": self._snapshot_company(company).model_dump(mode="python"),
                "recipient_snapshot": recipient_snapshot.model_dump(mode="python"),
                "items": [item.model_dump(mode="python") for item in items],
                "subtotal": subtotal,
                "vat_total": vat_total,
                "total": total,
                "amount_in_words": payload.amount_in_words,
            }
        )
        return await self.repo.create(doc)

    async def list_invoices(
        self, user_id: str, filters: InvoiceFilters, limit: int, offset: int
    ) -> list[InvoiceInDB]:
        return await self.repo.list_by_user(user_id, filters, limit, offset)

    async def get_invoice(self, user_id: str, invoice_id: str) -> InvoiceInDB:
        invoice = await self.repo.get_by_id(user_id, invoice_id)
        if invoice is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_INVOICE_NOT_FOUND_DETAIL)
        return invoice

    async def update_invoice(self, user_id: str, invoice_id: str, payload: InvoiceUpdate) -> InvoiceInDB:
        current = await self.get_invoice(user_id, invoice_id)
        update = payload.model_dump(exclude_unset=True, mode="python")

        if payload.status and payload.status != current.status:
            allowed = _ALLOWED_STATUS_TRANSITIONS.get(current.status, set())
            if payload.status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid invoice status transition",
                )

        updated = await self.repo.update_status_or_metadata(user_id, invoice_id, update)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_INVOICE_NOT_FOUND_DETAIL)
        return updated

