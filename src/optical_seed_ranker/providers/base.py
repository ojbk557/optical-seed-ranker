from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PatentQuery:
    cpc_prefixes: tuple[str, ...] = ("G02B9", "G02B13")
    keywords: tuple[str, ...] = ()
    published_after: date | None = None
    published_before: date | None = None
    limit: int = 100

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 100:
            raise ValueError("OPS-compatible query limit must be between 1 and 100")
        if (
            self.published_after
            and self.published_before
            and self.published_after > self.published_before
        ):
            raise ValueError("published_after cannot be later than published_before")


@dataclass(frozen=True, slots=True)
class PatentRecord:
    provider: str
    publication_number: str
    application_number: str | None
    family_id: str | None
    country: str
    title: str
    abstract: str | None
    applicants: tuple[str, ...]
    cpc_codes: tuple[str, ...]
    publication_date: date | None
    source_url: str
    full_text_available: bool
    images_available: bool
    raw_hash: str | None = None
    provider_metadata: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class PatentDocument:
    record: PatentRecord
    media_type: str
    content: bytes
    sha256: str
    retrieved_at_iso: str
    terms_reference: str


@runtime_checkable
class PatentProvider(Protocol):
    """Stable boundary around EPO, USPTO, BigQuery, or authorized WIPO APIs."""

    name: str

    def search(self, query: PatentQuery) -> Iterable[PatentRecord]: ...

    def fetch_document(self, publication_number: str) -> PatentDocument: ...
