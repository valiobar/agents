from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.models.financial.receipt import ExpenseDraft
from app.models.inventory.import_previews import (
    InventoryImportPreviewResponse,
    InventoryImportResult,
)
from app.models.shared.document import DocumentResponse

ClassifiedDocumentType = Literal[
    "receipt",
    "supplier_invoice",
    "contract",
    "csv_inventory_import",
    "json_data_import",
    "unknown",
]


class DocumentClassification(BaseModel):
    document_type: ClassifiedDocumentType
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class DocumentIntakeDraftResponse(BaseModel):
    classification: DocumentClassification
    document: DocumentResponse | None = None
    draft: ExpenseDraft | None = None
    extracted_text: str | None = None
    provider: str | None = None
    model: str | None = None
    extracted_at: datetime | None = None


class ReceiptExpenseReviewResponse(BaseModel):
    type: Literal["receipt_expense_review"] = "receipt_expense_review"
    classification: DocumentClassification
    document: DocumentResponse
    draft: ExpenseDraft
    extracted_text: str | None = None
    provider: str
    model: str
    extracted_at: datetime


class SupplierInvoiceInventoryReviewResponse(ReceiptExpenseReviewResponse):
    type: Literal["supplier_invoice_inventory_review"] = "supplier_invoice_inventory_review"
    inventory_import_preview: InventoryImportPreviewResponse


class SupplierInvoiceExpenseReviewResponse(ReceiptExpenseReviewResponse):
    type: Literal["supplier_invoice_expense_review"] = "supplier_invoice_expense_review"


class ConfirmInventoryImportForExpenseRequest(BaseModel):
    preview_id: str
    draft: ExpenseDraft


class ConfirmInventoryImportForExpenseResponse(BaseModel):
    type: Literal["supplier_invoice_expense_review"] = "supplier_invoice_expense_review"
    inventory_import_result: InventoryImportResult
    inventory_import_preview: InventoryImportPreviewResponse
    draft: ExpenseDraft


class UnknownDocumentReviewResponse(BaseModel):
    type: Literal["unknown_document_review"] = "unknown_document_review"
    classification: DocumentClassification
    document: DocumentResponse | None = None
    extracted_text: str | None = None
    warnings: list[str] = Field(default_factory=list)


DocumentIntakeResponse = Annotated[
    Union[
        ReceiptExpenseReviewResponse,
        SupplierInvoiceInventoryReviewResponse,
        SupplierInvoiceExpenseReviewResponse,
        UnknownDocumentReviewResponse,
    ],
    Field(discriminator="type"),
]


__all__ = [
    "ClassifiedDocumentType",
    "DocumentClassification",
    "DocumentIntakeDraftResponse",
    "DocumentIntakeResponse",
    "ReceiptExpenseReviewResponse",
    "SupplierInvoiceInventoryReviewResponse",
    "SupplierInvoiceExpenseReviewResponse",
    "ConfirmInventoryImportForExpenseRequest",
    "ConfirmInventoryImportForExpenseResponse",
    "UnknownDocumentReviewResponse",
]
