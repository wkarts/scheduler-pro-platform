from pathlib import Path


FORBIDDEN = (
    "evolution api",
    "cloudflare",
    "rabbitmq",
    "redis",
    "minio",
    "postgresql",
    "grafana",
    "prometheus",
    "portainer",
)


def test_user_facing_vue_surfaces_do_not_expose_private_technology_names() -> None:
    root = Path(__file__).resolve().parents[3]
    targets = [root / "apps" / "web" / "src", root / "apps" / "admin" / "src"]
    violations: list[str] = []
    for target in targets:
        for path in sorted(target.rglob("*.vue")):
            content = path.read_text(encoding="utf-8").lower()
            for forbidden in FORBIDDEN:
                if forbidden in content:
                    violations.append(f"{path.relative_to(root)} -> {forbidden}")
    assert not violations, "Nomes técnicos privados encontrados em superfícies visuais:\n" + "\n".join(violations)
