from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from urllib.parse import quote, unquote

from .models import SeedRecord

LOCAL_PROVIDER = "local"
PATENT_PROVIDER = "patent"
KNOWN_PROVIDERS = frozenset({LOCAL_PROVIDER, PATENT_PROVIDER})


def provider_for_seed(seed: SeedRecord) -> str:
    """Return the provider namespace used by the current two-source ranker."""

    return seed.provider


def make_seed_handle(provider: str, seed_id: str) -> str:
    if provider not in KNOWN_PROVIDERS:
        raise ValueError(f"unknown seed provider {provider!r}")
    if not seed_id:
        raise ValueError("seed_id cannot be empty")
    return f"{provider}:{quote(seed_id, safe='')}"


def seed_handle(seed: SeedRecord) -> str:
    return make_seed_handle(provider_for_seed(seed), seed.seed_id)


def parse_seed_handle(selector: str) -> tuple[str | None, str]:
    """Parse handle syntax; the resolver also checks historic bare-ID matches."""

    provider, separator, encoded_id = selector.partition(":")
    if not separator or provider not in KNOWN_PROVIDERS:
        return None, selector
    return provider, unquote(encoded_id)


def resolve_seed_selector(
    selector: str,
    *,
    local_seed_ids: Iterable[str],
    patent_seed_ids: Iterable[str],
) -> tuple[str, str]:
    """Resolve a handle, or a legacy bare ID when it has exactly one match."""

    counters = {
        LOCAL_PROVIDER: Counter(local_seed_ids),
        PATENT_PROVIDER: Counter(patent_seed_ids),
    }
    bare_counts = {
        provider: counter[selector] for provider, counter in counters.items()
    }
    bare_match_count = sum(bare_counts.values())
    requested_provider, qualified_seed_id = parse_seed_handle(selector)
    if requested_provider is not None:
        qualified_count = counters[requested_provider][qualified_seed_id]
        if qualified_count and bare_match_count:
            # The usual handle equals the ambiguous input here. Percent-encode
            # its first character to offer an alternative that selects the
            # qualified record instead of repeating the same unusable spelling.
            escaped_first = "".join(
                f"%{byte:02X}" for byte in qualified_seed_id[0].encode("utf-8")
            )
            explicit_handle = (
                f"{requested_provider}:{escaped_first}"
                f"{quote(qualified_seed_id[1:], safe='')}"
            )
            alternatives = [
                explicit_handle,
                *(
                    make_seed_handle(provider, selector)
                    for provider in (LOCAL_PROVIDER, PATENT_PROVIDER)
                    if bare_counts[provider]
                ),
            ]
            raise ValueError(
                f"seed selector {selector!r} is ambiguous between a qualified "
                "handle and a historic bare ID; use one of: "
                + ", ".join(alternatives)
            )
        if qualified_count > 1:
            raise ValueError(f"seed handle {selector!r} is not unique")
        if qualified_count == 1:
            return requested_provider, qualified_seed_id
        if bare_match_count == 0 and not qualified_seed_id:
            raise ValueError("a provider-qualified seed handle must include a seed_id")
        if bare_match_count == 0:
            raise KeyError(
                f"seed handle {selector!r} is not present in the {requested_provider} "
                "provider"
            )

    if bare_match_count == 0:
        raise KeyError(f"seed_id {selector!r} is not present in a configured provider")
    if bare_match_count > 1:
        handles = ", ".join(
            make_seed_handle(provider, selector)
            for provider in (LOCAL_PROVIDER, PATENT_PROVIDER)
            if bare_counts[provider]
        )
        raise ValueError(
            f"seed_id {selector!r} is ambiguous; use a provider-qualified handle: "
            f"{handles}"
        )
    provider = next(provider for provider, count in bare_counts.items() if count)
    return provider, selector
