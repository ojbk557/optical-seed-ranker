from datetime import date
from urllib.parse import parse_qs, urlparse

from optical_seed_ranker.providers.base import PatentQuery
from optical_seed_ranker.providers.epo_ops import EpoOpsProvider, HttpResponse, TOKEN_URL


SEARCH_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:e="http://www.epo.org/exchange">
  <ops:biblio-search total-result-count="1">
    <e:exchange-documents>
      <e:exchange-document country="EP" doc-number="1234567" kind="A1" date="20240214" family-id="42">
        <e:application-reference><e:document-id><e:doc-number>EP23123456</e:doc-number></e:document-id></e:application-reference>
        <e:invention-title lang="en">Large aperture imaging objective</e:invention-title>
        <e:abstract lang="en"><e:p>An objective with multiple lens groups.</e:p></e:abstract>
        <e:applicants><e:applicant><e:applicant-name><e:name>Example Optics</e:name></e:applicant-name></e:applicant></e:applicants>
        <e:patent-classifications><e:patent-classification><e:classification-symbol>G02B9/64</e:classification-symbol></e:patent-classification></e:patent-classifications>
      </e:exchange-document>
    </e:exchange-documents>
  </ops:biblio-search>
</ops:world-patent-data>"""


def test_build_cql_is_optics_scoped_and_date_bounded():
    query = PatentQuery(
        cpc_prefixes=("G02B9", "G02B13"),
        keywords=("large aperture",),
        published_after=date(2020, 1, 1),
        published_before=date(2024, 12, 31),
        limit=25,
    )
    cql = EpoOpsProvider.build_cql(query)
    assert "cpc=/low G02B9" in cql
    assert 'txt all "large aperture"' in cql
    assert 'pd within "20200101 20241231"' in cql


def test_provider_authenticates_once_and_parses_search_response():
    calls = []

    def fake_request(method, url, headers, body):
        calls.append((method, url, headers, body))
        if url == TOKEN_URL:
            return HttpResponse(
                200,
                {"Content-Type": "application/json"},
                b'{"access_token":"test-token","expires_in":1200}',
            )
        return HttpResponse(200, {"Content-Type": "application/exchange+xml"}, SEARCH_XML)

    provider = EpoOpsProvider("key", "secret", requester=fake_request)
    records = list(provider.search(PatentQuery(limit=10)))
    assert len(records) == 1
    record = records[0]
    assert record.publication_number == "EP1234567A1"
    assert record.title == "Large aperture imaging objective"
    assert record.applicants == ("Example Optics",)
    assert record.cpc_codes == ("G02B9/64",)
    assert record.publication_date == date(2024, 2, 14)

    provider.fetch_document("EP1234567A1")
    assert sum(1 for _, url, _, _ in calls if url == TOKEN_URL) == 1
    search_call = calls[1]
    assert search_call[2]["Authorization"] == "Bearer test-token"
    assert search_call[2]["X-OPS-Range"] == "1-10"
    assert "cpc=/low G02B9" in parse_qs(urlparse(search_call[1]).query)["q"][0]


def test_query_limit_matches_ops_range_limit():
    for bad in (0, 101):
        try:
            PatentQuery(limit=bad)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid OPS range was accepted")
