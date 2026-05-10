from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.company.repositories.company_repo import CompanyRepository
from app.financial.repositories.expense_repo import ExpenseRepository
from app.financial.repositories.invoice_repo import InvoiceRepository
from app.inventory.repositories.inventory_import_preview_repo import InventoryImportPreviewRepository
from app.inventory.repositories.inventory_item_repo import InventoryItemRepository
from app.inventory.repositories.inventory_location_repo import InventoryLocationRepository
from app.inventory.repositories.stock_movement_repo import StockMovementRepository
from app.partner.repositories.partner_repo import PartnerRepository
from app.company.services.company_service import CompanyService
from app.financial.services.expense_service import ExpenseService
from app.financial.services.financial_summary_service import FinancialSummaryService
from app.financial.services.invoice_service import InvoiceService
from app.inventory.services.inventory_import_service import InventoryImportService
from app.inventory.services.inventory_reporting_service import InventoryReportingService
from app.inventory.services.inventory_search_service import InventorySearchService
from app.inventory.services.inventory_service import InventoryService
from app.partner.services.partner_service import PartnerService
from app.utils.db import get_database


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-user-id header",
        )
    return x_user_id


def get_db() -> AsyncIOMotorDatabase:
    return get_database()


def get_company_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> CompanyRepository:
    return CompanyRepository(db)


def get_invoice_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> InvoiceRepository:
    return InvoiceRepository(db)


def get_expense_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> ExpenseRepository:
    return ExpenseRepository(db)


def get_partner_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> PartnerRepository:
    return PartnerRepository(db)


def get_inventory_item_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> InventoryItemRepository:
    return InventoryItemRepository(db)


def get_inventory_location_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> InventoryLocationRepository:
    return InventoryLocationRepository(db)


def get_stock_movement_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> StockMovementRepository:
    return StockMovementRepository(db)


def get_inventory_import_preview_repo(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InventoryImportPreviewRepository:
    return InventoryImportPreviewRepository(db)


def get_company_service(
    company_repo: CompanyRepository = Depends(get_company_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    partner_repo: PartnerRepository = Depends(get_partner_repo),
) -> CompanyService:
    return CompanyService(
        company_repo=company_repo,
        invoice_repo=invoice_repo,
        partner_repo=partner_repo,
    )


def get_expense_service(
    repo: ExpenseRepository = Depends(get_expense_repo),
    company_service: CompanyService = Depends(get_company_service),
    partner_repo: PartnerRepository = Depends(get_partner_repo),
) -> ExpenseService:
    return ExpenseService(repo, company_service=company_service, partner_repo=partner_repo)


def get_partner_service(
    partner_repo: PartnerRepository = Depends(get_partner_repo),
    company_service: CompanyService = Depends(get_company_service),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
) -> PartnerService:
    return PartnerService(
        partner_repo=partner_repo,
        company_service=company_service,
        invoice_repo=invoice_repo,
    )


def get_financial_summary_service(
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    expense_repo: ExpenseRepository = Depends(get_expense_repo),
    company_service: CompanyService = Depends(get_company_service),
    partner_service: PartnerService = Depends(get_partner_service),
) -> FinancialSummaryService:
    return FinancialSummaryService(invoice_repo, expense_repo, company_service, partner_service)


def get_inventory_service(
    item_repo: InventoryItemRepository = Depends(get_inventory_item_repo),
    location_repo: InventoryLocationRepository = Depends(get_inventory_location_repo),
    movement_repo: StockMovementRepository = Depends(get_stock_movement_repo),
    company_service: CompanyService = Depends(get_company_service),
) -> InventoryService:
    return InventoryService(
        item_repo=item_repo,
        location_repo=location_repo,
        movement_repo=movement_repo,
        company_service=company_service,
    )


def get_invoice_service(
    repo: InvoiceRepository = Depends(get_invoice_repo),
    company_service: CompanyService = Depends(get_company_service),
    partner_repo: PartnerRepository = Depends(get_partner_repo),
    inventory_service: InventoryService = Depends(get_inventory_service),
) -> InvoiceService:
    return InvoiceService(
        repo,
        company_service=company_service,
        partner_repo=partner_repo,
        inventory_service=inventory_service,
    )


def get_inventory_search_service(
    item_repo: InventoryItemRepository = Depends(get_inventory_item_repo),
    movement_repo: StockMovementRepository = Depends(get_stock_movement_repo),
    company_service: CompanyService = Depends(get_company_service),
) -> InventorySearchService:
    return InventorySearchService(
        item_repo=item_repo,
        movement_repo=movement_repo,
        company_service=company_service,
    )


def get_inventory_import_service(
    preview_repo: InventoryImportPreviewRepository = Depends(get_inventory_import_preview_repo),
    item_repo: InventoryItemRepository = Depends(get_inventory_item_repo),
    location_repo: InventoryLocationRepository = Depends(get_inventory_location_repo),
    movement_repo: StockMovementRepository = Depends(get_stock_movement_repo),
    company_service: CompanyService = Depends(get_company_service),
) -> InventoryImportService:
    return InventoryImportService(
        preview_repo=preview_repo,
        item_repo=item_repo,
        location_repo=location_repo,
        movement_repo=movement_repo,
        company_service=company_service,
    )


def get_inventory_reporting_service(
    item_repo: InventoryItemRepository = Depends(get_inventory_item_repo),
    location_repo: InventoryLocationRepository = Depends(get_inventory_location_repo),
    movement_repo: StockMovementRepository = Depends(get_stock_movement_repo),
    company_service: CompanyService = Depends(get_company_service),
) -> InventoryReportingService:
    return InventoryReportingService(
        item_repo=item_repo,
        location_repo=location_repo,
        movement_repo=movement_repo,
        company_service=company_service,
    )
