from app.services.template_contract import CONTRACT_SCHEMA, TemplateContract


def test_example_package_is_valid_and_contains_both_surfaces() -> None:
    bundle = TemplateContract.example_package()
    report = TemplateContract.validate_package(bundle)
    assert bundle["schema"] == CONTRACT_SCHEMA
    assert report["valid"] is True
    assert set(report["surfaces"]) == {"landing", "booking"}


def test_landing_rejects_unknown_renderer_block() -> None:
    bundle = TemplateContract.example_package()
    landing = bundle["package"]["surfaces"]["landing"]
    landing["blocks"].append(
        {
            "id": "unsafe-1",
            "type": "script_widget",
            "props": {},
            "style": {},
            "responsive": {
                "desktop": {},
                "tablet": {},
                "mobile": {},
                "hidden": {"desktop": False, "tablet": False, "mobile": False},
            },
        }
    )
    report = TemplateContract.validate_package(bundle)
    assert report["valid"] is False
    assert any(
        item["code"] == "LANDING_BLOCK_TYPE_UNSUPPORTED"
        for item in report["errors"]
    )


def test_booking_requires_copy_contract() -> None:
    bundle = TemplateContract.example_package()
    booking = bundle["package"]["surfaces"]["booking"]
    booking.pop("copy")
    report = TemplateContract.validate_package(bundle)
    assert report["valid"] is False
    assert any(item["code"] == "BOOKING_COPY_REQUIRED" for item in report["errors"])


def test_single_surface_package_is_valid_with_pair_warning() -> None:
    bundle = TemplateContract.example_package()
    bundle["package"]["surfaces"].pop("booking")
    report = TemplateContract.validate_package(bundle)
    assert report["valid"] is True
    assert any(item["code"] == "PACKAGE_PAIR_RECOMMENDED" for item in report["warnings"])


def test_contract_declares_canonical_import_location() -> None:
    descriptor = TemplateContract.descriptor()
    assert descriptor["schema"] == CONTRACT_SCHEMA
    assert "Control Plane" in descriptor["canonical_import_location"]
    assert "LANDING" in descriptor["surfaces"]
    assert "BOOKING" in descriptor["surfaces"]
