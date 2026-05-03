from __future__ import annotations


class KnowledgeBaseError(Exception):
    status_code: int = 500
    detail: str = "Knowledge Base error"


class UnsupportedDocumentTypeError(KnowledgeBaseError):
    status_code = 415

    def __init__(self, content_type: str) -> None:
        self.detail = f"Unsupported document type: {content_type}"
        self.content_type = content_type


class UploadTooLargeError(KnowledgeBaseError):
    status_code = 413
    detail = "Uploaded file exceeds maximum allowed size"


class EmptyDocumentError(KnowledgeBaseError):
    status_code = 400
    detail = "Document did not contain extractable text"


class ExpenseExtractionFailedError(KnowledgeBaseError):
    status_code = 502

    def __init__(self, message: str = "Expense extraction failed") -> None:
        self.detail = message


class DocumentNotFoundError(KnowledgeBaseError):
    status_code = 404

    def __init__(self, document_id: str) -> None:
        self.detail = f"Document not found: {document_id}"
        self.document_id = document_id


class IngestionFailedError(KnowledgeBaseError):
    status_code = 500

    def __init__(self, message: str) -> None:
        self.detail = message

