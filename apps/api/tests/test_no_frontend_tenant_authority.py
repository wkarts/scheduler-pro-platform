from pathlib import Path

CONTROL_PLANE_ROUTE_MODULES = {
    "platform.py",
    "platform_access.py",
    "tenant_management.py",
    "tenant_support.py",
    "platform_templates.py",
    "builds.py",
    "observability.py",
}


def test_tenant_facing_routes_do_not_accept_tenant_id_as_authority() -> None:
    routes = Path("app/api/v1/routes").glob("*.py")
    bad: list[str] = []
    for path in routes:
        if path.name in CONTROL_PLANE_ROUTE_MODULES:
            continue
        source = path.read_text(encoding="utf-8")
        if "tenant_id:" in source:
            bad.append(str(path))
    assert not bad, (
        "Tenant-facing authority must come from hostname/context, not request "
        f"body/query: {bad}"
    )


def test_control_plane_modules_with_tenant_scope_require_platform_authorization() -> None:
    routes_dir = Path("app/api/v1/routes")
    for name in CONTROL_PLANE_ROUTE_MODULES - {"platform.py"}:
        source = (routes_dir / name).read_text(encoding="utf-8")
        if "tenant_id:" not in source:
            continue
        assert (
            "require_platform_permission" in source
            or "require_super_admin" in source
        ), f"Control-plane route {name} accepts tenant scope without platform authorization"
