from pathlib import Path


def test_routes_do_not_accept_tenant_id_as_authority():
    routes = Path("app/api/v1/routes").glob("*.py")
    bad = []
    for path in routes:
        text = path.read_text(encoding="utf-8")
        if "tenant_id:" in text and "platform.py" not in str(path):
            bad.append(str(path))
    assert not bad, f"Tenant authority must come from hostname/context, not request body/query: {bad}"
