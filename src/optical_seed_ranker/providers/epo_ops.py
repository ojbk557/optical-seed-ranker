from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Iterable, Mapping

from .base import PatentDocument, PatentQuery, PatentRecord

TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
REST_ROOT = "https://ops.epo.org/3.2/rest-services"
TERMS_URL = "https://www.epo.org/en/searching-for-patents/data/web-services/ops"


class EpoOpsError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


HttpRequester = Callable[[str, str, Mapping[str, str], bytes | None], HttpResponse]


def _default_requester(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return HttpResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except urllib.error.HTTPError as error:
        raise EpoOpsError(
            "EPO OPS returned HTTP %s: %s" % (error.code, error.read().decode("utf-8", "replace"))
        ) from error
    except urllib.error.URLError as error:
        raise EpoOpsError("EPO OPS request failed: %s" % error.reason) from error


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in element.iter() if _local_name(item.tag) == name]


def _first_text(element: ET.Element, name: str) -> str | None:
    for item in _children(element, name):
        value = " ".join("".join(item.itertext()).split())
        if value:
            return value
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    compact = value.replace("-", "")
    try:
        return datetime.strptime(compact, "%Y%m%d").date()
    except ValueError:
        return None


class EpoOpsProvider:
    """Small EPO OPS adapter with injected HTTP for deterministic offline tests."""

    name = "epo_ops"

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        requester: HttpRequester | None = None,
    ) -> None:
        if not consumer_key or not consumer_secret:
            raise ValueError("EPO OPS consumer key and secret are required")
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self._requester = requester or _default_requester
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @classmethod
    def from_environment(cls, requester: HttpRequester | None = None) -> "EpoOpsProvider":
        return cls(
            os.environ.get("EPO_OPS_KEY", ""),
            os.environ.get("EPO_OPS_SECRET", ""),
            requester=requester,
        )

    def _token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token
        raw = (self.consumer_key + ":" + self.consumer_secret).encode("utf-8")
        basic = base64.b64encode(raw).decode("ascii")
        response = self._requester(
            "POST",
            TOKEN_URL,
            {
                "Authorization": "Basic " + basic,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            b"grant_type=client_credentials",
        )
        if response.status != 200:
            raise EpoOpsError("EPO OPS token request returned HTTP %s" % response.status)
        try:
            payload = json.loads(response.body.decode("utf-8"))
            token = str(payload["access_token"])
            expires_in = int(payload.get("expires_in", 1200))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise EpoOpsError("EPO OPS token response is invalid") from error
        self._access_token = token
        self._token_expires_at = time.time() + max(60, expires_in)
        return token

    @staticmethod
    def build_cql(query: PatentQuery) -> str:
        clauses: list[str] = []
        if query.cpc_prefixes:
            cpc = ["cpc=/low %s" % item.strip() for item in query.cpc_prefixes if item.strip()]
            clauses.append("(" + " or ".join(cpc) + ")")
        for keyword in query.keywords:
            clean = " ".join(keyword.replace('"', " ").split())
            if clean:
                clauses.append('txt all "%s"' % clean)
        if query.published_after and query.published_before:
            clauses.append(
                'pd within "%s %s"'
                % (
                    query.published_after.strftime("%Y%m%d"),
                    query.published_before.strftime("%Y%m%d"),
                )
            )
        elif query.published_after:
            clauses.append("pd >= %s" % query.published_after.strftime("%Y%m%d"))
        elif query.published_before:
            clauses.append("pd <= %s" % query.published_before.strftime("%Y%m%d"))
        return " and ".join(clauses) or "cpc=/low G02B"

    def _get(self, path: str, *, query: Mapping[str, str] | None = None, limit: int | None = None) -> HttpResponse:
        url = REST_ROOT + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        headers = {
            "Authorization": "Bearer " + self._token(),
            "Accept": "application/exchange+xml",
        }
        if limit is not None:
            headers["X-OPS-Range"] = "1-%d" % limit
        response = self._requester("GET", url, headers, None)
        if response.status != 200:
            raise EpoOpsError("EPO OPS data request returned HTTP %s" % response.status)
        return response

    def search(self, query: PatentQuery) -> Iterable[PatentRecord]:
        response = self._get(
            "/published-data/search/biblio,abstract",
            query={"q": self.build_cql(query)},
            limit=query.limit,
        )
        return self._parse_search(response.body)[: query.limit]

    def fetch_document(self, publication_number: str) -> PatentDocument:
        normalized = "".join(publication_number.split())
        if not normalized:
            raise ValueError("publication_number cannot be empty")
        quoted = urllib.parse.quote(normalized, safe=".")
        response = self._get(
            "/published-data/publication/epodoc/%s/biblio" % quoted
        )
        return PatentDocument(
            record=self._parse_search(response.body)[0],
            media_type="application/exchange+xml",
            content=response.body,
            sha256=hashlib.sha256(response.body).hexdigest(),
            retrieved_at_iso=datetime.now(timezone.utc).isoformat(),
            terms_reference=TERMS_URL,
        )

    def _parse_search(self, xml: bytes) -> list[PatentRecord]:
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as error:
            raise EpoOpsError("EPO OPS returned malformed XML") from error
        records: list[PatentRecord] = []
        raw_hash = hashlib.sha256(xml).hexdigest()
        for document in _children(root, "exchange-document"):
            country = document.attrib.get("country", "")
            number = document.attrib.get("doc-number", "")
            kind = document.attrib.get("kind", "")
            publication_number = country + number + kind
            if not publication_number:
                continue
            titles = _children(document, "invention-title")
            title = ""
            for item in titles:
                value = " ".join("".join(item.itertext()).split())
                if value and (not title or item.attrib.get("lang") == "en"):
                    title = value
                    if item.attrib.get("lang") == "en":
                        break
            abstract_node = next(iter(_children(document, "abstract")), None)
            abstract = None
            if abstract_node is not None:
                abstract = " ".join("".join(abstract_node.itertext()).split()) or None
            applicants = tuple(
                dict.fromkeys(
                    value
                    for item in _children(document, "applicant-name")
                    if (value := _first_text(item, "name"))
                )
            )
            cpc_codes = tuple(
                dict.fromkeys(
                    "".join(item.itertext()).strip()
                    for item in _children(document, "classification-symbol")
                    if "".join(item.itertext()).strip()
                )
            )
            application_reference = next(
                iter(_children(document, "application-reference")), None
            )
            application_number = (
                _first_text(application_reference, "doc-number")
                if application_reference is not None
                else None
            )
            publication_date = _parse_date(document.attrib.get("date"))
            if publication_date is None:
                publication_date = _parse_date(_first_text(document, "date"))
            source_url = (
                REST_ROOT
                + "/published-data/publication/epodoc/"
                + publication_number
                + "/biblio"
            )
            records.append(
                PatentRecord(
                    provider=self.name,
                    publication_number=publication_number,
                    application_number=application_number,
                    family_id=document.attrib.get("family-id"),
                    country=country,
                    title=title or publication_number,
                    abstract=abstract,
                    applicants=applicants,
                    cpc_codes=cpc_codes,
                    publication_date=publication_date,
                    source_url=source_url,
                    full_text_available=False,
                    images_available=False,
                    raw_hash=raw_hash,
                    provider_metadata={"kind": kind},
                )
            )
        if not records:
            raise EpoOpsError("EPO OPS response contained no exchange documents")
        return records
