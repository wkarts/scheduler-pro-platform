import re
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


def _contains_private_term(content: str, term: str) -> bool:
    """Detecta o nome técnico como termo, não como trecho de outra palavra.

    Exemplo importante: ``dominios`` contém acidentalmente a sequência
    ``minio``. Isso não representa exposição do produto de armazenamento e não
    deve falhar o contrato de white-label.
    """
    pattern = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
    return re.search(pattern, content, flags=re.IGNORECASE) is not None


def test_user_facing_vue_surfaces_do_not_expose_private_technology_names() -> None:
    root = Path(__file__).resolve().parents[3]
    targets = [root / "apps" / "web" / "src", root / "apps" / "admin" / "src"]
    violations: list[str] = []
    for target in targets:
        for path in sorted(target.rglob("*.vue")):
            content = path.read_text(encoding="utf-8")
            for forbidden in FORBIDDEN:
                if _contains_private_term(content, forbidden):
                    violations.append(f"{path.relative_to(root)} -> {forbidden}")
    assert not violations, "Nomes técnicos privados encontrados em superfícies visuais:\n" + "\n".join(violations)


def test_white_label_detector_does_not_confuse_portuguese_domains_with_minio() -> None:
    assert _contains_private_term("Domínios e DNS", "minio") is False
    assert _contains_private_term("dominios", "minio") is False
    assert _contains_private_term("MinIO", "minio") is True
