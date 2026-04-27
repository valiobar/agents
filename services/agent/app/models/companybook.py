from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.partner import PartnerCreate, PartnerKind


def _none_if_blank(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _first_non_blank(*values: str | None) -> str | None:
    for value in values:
        if value and value.strip():
            return value.strip()
    return None


def _normalize_person(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _first_non_blank(
            _value_as_str(value.get("name")),
            _value_as_str(value.get("fullName")),
            _value_as_str(value.get("full_name")),
        )
    return None


def _value_as_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, bool):
        return "active" if value else "inactive"
    if isinstance(value, int | float):
        return str(value)
    return None


class CompanyBookPartnerMappingError(ValueError):
    def __init__(self, missing_fields: list[str], partner_draft: dict[str, Any]) -> None:
        self.missing_fields = missing_fields
        self.partner_draft = partner_draft
        fields = ", ".join(missing_fields)
        super().__init__(f"CompanyBook data is missing required partner fields: {fields}")


class CompanyBookSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    uic: str = Field(validation_alias=AliasChoices("uic", "UIC", "registration_number"))
    name: str
    legal_form: str | None = Field(
        default=None,
        validation_alias=AliasChoices("legalForm", "legal_form", "legal_form_name"),
    )
    status: str | None = None
    transliteration: str | None = None

    @field_validator("uic", "name", "legal_form", "status", "transliteration", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object | None:
        return _none_if_blank(_value_as_str(value))


class CompanyBookSearchResponse(BaseModel):
    results: list[CompanyBookSearchResult]
    total: int | None = None

    @classmethod
    def from_api(cls, payload: object) -> CompanyBookSearchResponse:
        if isinstance(payload, list):
            return cls(results=[CompanyBookSearchResult.model_validate(item) for item in payload])

        if not isinstance(payload, dict):
            return cls(results=[])

        raw_results = (
            payload.get("results")
            or payload.get("companies")
            or payload.get("data")
            or payload.get("items")
            or []
        )
        if isinstance(raw_results, dict):
            raw_results = raw_results.get("results") or raw_results.get("companies") or raw_results.get("items") or []
        if not isinstance(raw_results, list):
            raw_results = []

        total = payload.get("total") or payload.get("count")
        return cls(
            results=[CompanyBookSearchResult.model_validate(item) for item in raw_results],
            total=total if isinstance(total, int) else None,
        )


class CompanyBookSeat(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    country: str | None = None
    district: str | None = None
    municipality: str | None = None
    settlement: str | None = Field(
        default=None,
        validation_alias=AliasChoices("settlement", "city", "town", "place"),
    )
    address: str | None = None

    @model_validator(mode="before")
    @classmethod
    def compose_address(cls, data: object) -> object:
        if not isinstance(data, dict) or data.get("address"):
            return data

        parts = [
            _value_as_str(data.get("street")),
            _value_as_str(data.get("streetNumber") or data.get("street_number")),
            _value_as_str(data.get("block")),
            _value_as_str(data.get("entrance")),
            _value_as_str(data.get("floor")),
            _value_as_str(data.get("apartment")),
        ]
        address = ", ".join(part for part in parts if part)
        return {**data, "address": address or None}

    @field_validator("country", "district", "municipality", "settlement", "address", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object | None:
        return _none_if_blank(_value_as_str(value))


class CompanyBookContacts(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    email: str | None = Field(default=None, validation_alias=AliasChoices("email", "e_mail"))
    phone: str | None = Field(default=None, validation_alias=AliasChoices("phone", "telephone", "tel"))

    @field_validator("email", "phone", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object | None:
        return _none_if_blank(_value_as_str(value))


class CompanyBookCompanyDetail(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    uic: str = Field(validation_alias=AliasChoices("uic", "UIC", "registration_number"))
    name: str
    legal_form: str | None = Field(
        default=None,
        validation_alias=AliasChoices("legalForm", "legal_form", "legal_form_name"),
    )
    seat: CompanyBookSeat | None = None
    contacts: CompanyBookContacts | None = None
    managers: list[str] = Field(default_factory=list)

    @classmethod
    def from_api(cls, payload: object) -> CompanyBookCompanyDetail:
        if isinstance(payload, dict):
            data = payload.get("company") or payload.get("data") or payload.get("result") or payload
            if isinstance(data, dict):
                return cls.model_validate(data)
        return cls.model_validate(payload)

    @field_validator("uic", "name", "legal_form", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> object | None:
        return _none_if_blank(_value_as_str(value))

    @field_validator("managers", mode="before")
    @classmethod
    def normalize_managers(cls, value: object) -> list[str]:
        raw_values: list[object]
        if value is None:
            raw_values = []
        elif isinstance(value, list):
            raw_values = value
        else:
            raw_values = [value]

        managers = [_normalize_person(item) for item in raw_values]
        return [manager for manager in managers if manager]

    @model_validator(mode="before")
    @classmethod
    def collect_representatives(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        mapped = dict(data)
        if not mapped.get("name") and isinstance(mapped.get("companyName"), dict):
            mapped["name"] = _value_as_str(mapped["companyName"].get("name"))

        if mapped.get("managers"):
            return mapped

        representatives = (
            mapped.get("representatives")
            or mapped.get("representativesList")
            or mapped.get("management")
            or mapped.get("owners")
        )
        if representatives:
            mapped["managers"] = representatives
        return mapped

    def partner_draft(self, company_id: str, kind: PartnerKind) -> dict[str, Any]:
        seat = self.seat or CompanyBookSeat()
        contacts = self.contacts or CompanyBookContacts()
        city = _first_non_blank(seat.settlement, seat.municipality, seat.district)
        accountable_person = self.managers[0] if self.managers else None

        return {
            "company_id": company_id,
            "kind": kind,
            "name": self.name,
            "registration_number": self.uic,
            "vat_number": f"BG{self.uic}" if self.uic else None,
            "city": city,
            "country": seat.country or "Bulgaria",
            "address": seat.address,
            "accountable_person": accountable_person,
            "email": contacts.email,
            "phone": contacts.phone,
            "notes": "Imported from CompanyBook.BG",
        }

    def to_partner_create(self, company_id: str, kind: PartnerKind) -> PartnerCreate:
        draft = self.partner_draft(company_id, kind)
        required_fields = [
            "name",
            "registration_number",
            "city",
            "country",
            "address",
            "accountable_person",
        ]
        missing_fields = [field for field in required_fields if not draft.get(field)]
        if missing_fields:
            raise CompanyBookPartnerMappingError(missing_fields, draft)
        return PartnerCreate.model_validate(draft)
