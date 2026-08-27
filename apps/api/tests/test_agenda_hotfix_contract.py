from pathlib import Path


def _repository_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir() and (parent / "apps" / "web").is_dir():
            return parent
    return Path.cwd()


ROOT = _repository_root()


def _read(path: str) -> str:
    candidates = [
        ROOT / path,
        ROOT / path.removeprefix("apps/api/"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def test_agenda_customer_reuse_null_email_is_typed_for_asyncpg() -> None:
    source = _read("apps/api/app/api/v1/routes/agenda.py")
    assert source
    assert "email=coalesce(cast(:email as varchar), email)" in source
    assert "email=case when :email is null then email else :email end" not in source


def test_business_hour_violation_is_a_domain_error_not_generic_failure() -> None:
    source = _read("apps/api/app/services/flexible_appointment_service.py")
    assert "APPOINTMENT_OUTSIDE_BUSINESS_HOURS" in source
    assert "fora do expediente configurado" in source
    assert "if not business_rows:" in source
    assert "return []" in source


def test_report_automation_exposes_edit_pause_resume_and_delete() -> None:
    source = _read("apps/web/src/TenantAgendaCenter.vue")
    if not source:
        # O container da suíte integration copia somente apps/api. A validação
        # completa do frontend ocorre no checkout do job unit/web.
        return
    for token in (
        "editSchedule",
        "toggleSchedule",
        "deleteSchedule",
        "Editar",
        "Pausar",
        "Ativar",
        "Excluir",
    ):
        assert token in source


def test_html_runtime_is_sandboxed_without_same_origin() -> None:
    source = _read("apps/web/src/HtmlTemplateFrame.vue")
    if not source:
        return
    assert "sandbox=\"allow-scripts" in source
    assert "allow-same-origin" not in source
    assert "scheduler-pro-html-api-request" in source
    assert "/api/v1/public/booking" in source
