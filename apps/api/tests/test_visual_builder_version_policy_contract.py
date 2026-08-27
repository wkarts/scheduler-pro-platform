import pytest

from app.core.errors import APIError
from app.services.visual_builder_version_service import (
    DEFAULT_VERSION,
    RELEASES,
    SUPPORTED_VERSIONS,
    _ordered_versions,
    _version,
)


def test_supported_releases_and_default_are_stable() -> None:
    assert SUPPORTED_VERSIONS == ("1.0.0", "2.0.0", "2.0.1")
    assert DEFAULT_VERSION == "2.0.1"
    assert [item["version"] for item in RELEASES] == list(SUPPORTED_VERSIONS)
    assert [item["schema"] for item in RELEASES] == [
        "argws-visual-builder/v2",
        "argws-visual-builder/v3",
        "argws-visual-builder/v3",
    ]
    assert RELEASES[-1]["recommended"] is True


def test_release_order_is_canonical_and_duplicates_are_removed() -> None:
    assert _ordered_versions(["2.0.1", "1.0.0", "2.0.1"]) == [
        "1.0.0",
        "2.0.1",
    ]


def test_unknown_release_is_rejected() -> None:
    with pytest.raises(APIError) as raised:
        _version("9.9.9")
    assert raised.value.code == "VISUAL_BUILDER_VERSION_UNSUPPORTED"
