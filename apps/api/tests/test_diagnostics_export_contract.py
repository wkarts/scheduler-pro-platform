import ast
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


def test_domain_reconciler_does_not_query_missing_created_at_column() -> None:
    worker = Path("app/workers/tasks.py").resolve().read_text(encoding="utf-8")
    reconciler = next(
        node for node in ast.walk(ast.parse(worker))
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_reconcile_managed_domains"
    )
    # Inspect the SQL argument itself; nesting it in aclosing must not change this contract.
    queries = [
        " ".join(node.args[0].value.lower().split())
        for node in ast.walk(reconciler)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "text"
        and node.args and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]
    domain_queries = [query for query in queries if query.startswith("select id::text from domains")]
    assert len(domain_queries) == 1, "Expected exactly one domain reconciliation query"
    query = domain_queries[0]

    assert "order by id asc" in query
    assert "created_at" not in query
