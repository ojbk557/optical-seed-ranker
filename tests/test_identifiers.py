import pytest

from optical_seed_ranker.identifiers import resolve_seed_selector
from optical_seed_ranker.models import SeedRecord


def test_seed_record_provider_does_not_shift_legacy_positional_fields():
    seed = SeedRecord(
        "legacy",
        "camera",
        100,
        2,
        20,
        4,
        2,
        "reference",
        "infinity",
        "source",
        "legacy.zmx",
        400,
        700,
        80,
        20,
        1,
        0,
    )

    assert seed.source_path == "legacy.zmx"
    assert seed.obsolete_glass_count == 0
    assert seed.provider == "local"


@pytest.mark.parametrize("selector", ["local:foo", "patent:legacy"])
def test_handle_like_historic_bare_id_falls_back_when_qualified_target_is_absent(selector):
    assert resolve_seed_selector(
        selector,
        local_seed_ids=[selector],
        patent_seed_ids=[],
    ) == ("local", selector)


def test_handle_and_historic_bare_id_collision_requires_encoded_handle():
    with pytest.raises(ValueError, match="historic bare ID") as error:
        resolve_seed_selector(
            "patent:legacy",
            local_seed_ids=["patent:legacy"],
            patent_seed_ids=["legacy"],
        )

    assert "patent:legacy" in str(error.value)
    assert "patent:%6Cegacy" in str(error.value)
    assert "local:patent%3Alegacy" in str(error.value)

    assert resolve_seed_selector(
        "patent:%6Cegacy",
        local_seed_ids=["patent:legacy"],
        patent_seed_ids=["legacy"],
    ) == ("patent", "legacy")


def test_legacy_local_id_and_qualified_local_id_can_both_be_selected():
    local_ids = ["foo", "local:foo"]
    with pytest.raises(ValueError, match="historic bare ID") as error:
        resolve_seed_selector("local:foo", local_seed_ids=local_ids, patent_seed_ids=[])

    assert "local:%66oo" in str(error.value)
    assert "local:local%3Afoo" in str(error.value)
    assert resolve_seed_selector(
        "local:%66oo", local_seed_ids=local_ids, patent_seed_ids=[]
    ) == ("local", "foo")
    assert resolve_seed_selector(
        "local:local%3Afoo", local_seed_ids=local_ids, patent_seed_ids=[]
    ) == ("local", "local:foo")


def test_percent_encoded_handle_selects_historic_colon_id_unambiguously():
    assert resolve_seed_selector(
        "local:patent%3Alegacy",
        local_seed_ids=["patent:legacy"],
        patent_seed_ids=["legacy"],
    ) == ("local", "patent:legacy")
