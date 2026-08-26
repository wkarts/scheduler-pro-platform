import pytest

from app.core.errors import APIError
from app.services.phone_normalization import PhoneNormalizationService, PhonePolicy


@pytest.fixture()
def br_phone() -> PhoneNormalizationService:
    return PhoneNormalizationService(
        PhonePolicy(
            country="BR",
            country_code="55",
            area_code="75",
            add_ninth_digit=True,
        )
    )


@pytest.mark.parametrize(
    "raw",
    [
        "88881111",
        "988881111",
        "7588881111",
        "75988881111",
        "(75) 98888-1111",
        "75 98888-1111",
        "+55 (75) 98888-1111",
        "55 75 98888 1111",
        "5575988881111",
    ],
)
def test_brazilian_variants_are_equivalent(
    br_phone: PhoneNormalizationService,
    raw: str,
) -> None:
    assert br_phone.normalize(raw, required=True) == "5575988881111"


def test_normalization_is_idempotent(br_phone: PhoneNormalizationService) -> None:
    first = br_phone.normalize("88881111", required=True)
    assert first == "5575988881111"
    assert br_phone.normalize(first, required=True) == first


def test_no_default_area_code_requires_explicit_ddd() -> None:
    service = PhoneNormalizationService(
        PhonePolicy(country="BR", country_code="55", area_code="", add_ninth_digit=True)
    )
    with pytest.raises(APIError) as exc:
        service.normalize("88881111", required=True)
    assert exc.value.code == "PHONE_AREA_CODE_REQUIRED"


def test_other_country_keeps_explicit_country_code() -> None:
    service = PhoneNormalizationService(
        PhonePolicy(country="US", country_code="1", area_code="305", add_ninth_digit=False)
    )
    assert service.normalize("13055551234", required=True) == "13055551234"
    assert service.normalize("5551234", required=True) == "13055551234"
