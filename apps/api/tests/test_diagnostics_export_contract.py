from pathlib import Path

from app.services.diagnostics_export_service import DiagnosticsExportService


def test_diagnostics_redacts_known_secret_fields_and_bearer_tokens() -> None:
    value = {
        "password": "super-secret",
        "nested": {
            "api_token": "token-value",
            "message": "Authorization: Bearer abc.def.ghi",
        },
    }

    redacted = DiagnosticsExportService._redact(value)

    assert redacted["password"] == "[REDACTED]"
    assert redacted["nested"]["api_token"] == "[REDACTED]"
    assert "abc.def.ghi" not in redacted["nested"]["message"]
    assert "[REDACTED]" in redacted["nested"]["message"]


def test_admin_has_diagnostics_download_and_frontend_telemetry() -> None:
    root = Path("../../apps/admin/src").resolve()
    main = (root / "main.ts").read_text(encoding="utf-8")
    download = (root / "diagnostics-download.ts").read_text(encoding="utf-8")
    telemetry = (root / "frontend-telemetry.ts").read_text(encoding="utf-8")

    assert "installDiagnosticsDownload" in main
    assert "installFrontendTelemetry" in main
    assert "Baixar logs completos (.zip)" in download
    assert "/platform/observability/logs/export" in download
    assert "browser_error" in telemetry
    assert "unhandled_rejection" in telemetry
    assert "console_error" in telemetry


def test_platform_migration_adds_domain_created_at_for_reconciler() -> None:
    migration = Path(
        "migrations/alembic_platform/versions/0009_domain_created_at.py"
    ).resolve().read_text(encoding="utf-8")

    assert 'revision = "platform_0009"' in migration
    assert 'down_revision = "platform_0008"' in migration
    assert "alter table domains" in migration
    assert "created_at timestamptz" in migration
