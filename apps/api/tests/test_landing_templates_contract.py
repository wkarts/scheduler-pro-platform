from app.services.landing_templates import list_templates, template_content


EXPECTED = {
    "martelinho-de-ouro": "Martelinho de Ouro",
    "cabeleireiro": "Cabeleireiro",
    "studio-neils": "Studio Neils",
    "clinica": "Clínica",
    "servicos": "Serviços",
    "reunioes": "Reuniões",
    "agenda-essencial": "Agenda Essencial",
}


def test_exactly_seven_professional_templates_exist() -> None:
    templates = list_templates()
    assert len(templates) == 7
    assert {item["key"]: item["name"] for item in templates} == EXPECTED


def test_templates_are_structurally_distinct_and_bookable() -> None:
    signatures: set[tuple[str, ...]] = set()
    for key in EXPECTED:
        content = template_content(key)
        blocks = content["blocks"]
        block_types = tuple(block["type"] for block in blocks)
        assert len(blocks) >= 7
        assert "hero" in block_types
        assert "booking" in block_types
        assert "footer" in block_types
        signatures.add(block_types)
    assert len(signatures) == 7


def test_template_returns_independent_copy() -> None:
    first = template_content("agenda-essencial")
    second = template_content("agenda-essencial")
    first["blocks"][0]["props"]["title"] = "mutated"
    assert second["blocks"][0]["props"]["title"] != "mutated"
