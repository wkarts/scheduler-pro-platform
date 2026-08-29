from pathlib import Path


def _repository_root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "api").is_dir() and (parent / "apps" / "web").is_dir():
            return parent
    return None


ROOT = _repository_root()


def _source(path: str) -> str:
    if ROOT is None:
        import pytest

        pytest.skip("Fontes do monorepo não fazem parte da imagem isolada da API.")
    return (ROOT / path).read_text(encoding="utf-8")


def test_checkin_center_is_global_like_agenda_operator() -> None:
    app = _source("apps/web/src/App.vue")
    center = _source("apps/web/src/TenantCheckInCenter.vue")
    operator = _source("apps/web/src/TenantAgendaOperator.vue")

    assert "TenantCheckInCenter" in app
    assert "<TenantCheckInCenter/>" in app
    assert 'TenantCheckInCenter v-if="activeView' not in app
    assert "sp-checkin-launcher" in center
    assert "sp-global-agenda-operator" in operator
    assert "bottom:80px" in center
    assert "bottom:22px" in operator
    assert "Central de Check-in" in center
    assert "Selecionar este horário" in center
    assert "Não compareceu" in center
    assert "Horário chegou · aguardando Check-in" in center
    assert "Atrasado ${deltaMinutes} min · aguardando Check-in" in center


def test_checkin_flow_defaults_to_full_and_supports_simple() -> None:
    service = _source("apps/api/app/services/booking_parameters_service.py")
    settings = _source("apps/api/app/api/v1/routes/settings.py")
    center = _source("apps/web/src/TenantCheckInCenter.vue")
    route = _source("apps/api/app/api/v1/routes/checkin.py")

    assert 'CHECKIN_FLOW_MODES = {"FULL", "SIMPLE"}' in service
    assert 'values.get("checkin_flow_mode") or "FULL"' in service
    assert '"checkin_flow_mode": checkin_flow_mode' in service
    assert 'Literal["FULL", "SIMPLE"] = "FULL"' in settings
    assert "flowMode=ref<CheckinFlowMode>('FULL')" in center
    assert '<option value="FULL">Completo</option>' in center
    assert '<option value="SIMPLE">Simplificado</option>' in center
    assert "fullFlow&&item.status==='CHECKED_IN'" in center
    assert "fullFlow&&item.status==='IN_PROGRESS'" in center
    assert "AppointmentStatus.completed.value" in route
    assert 'parameters.get("checkin_flow_mode") == "SIMPLE"' in route
    assert "Atendimento concluído automaticamente" in route


def test_checkin_is_manual_and_uses_dedicated_endpoint() -> None:
    center = _source("apps/web/src/TenantCheckInCenter.vue")
    route = _source("apps/api/app/api/v1/routes/checkin.py")
    router = _source("apps/api/app/api/v1/router.py")

    assert "Date.now()>=new Date(item.starts_at).getTime()" in center
    assert "await api(`/check-in/${item.id}`" in center
    assert "CHECK_IN_REQUIRES_CONFIRMATION" in route
    assert "current_status != AppointmentStatus.confirmed.value" in route
    assert "Check-in realizado pela Central de Check-in" in route
    assert 'prefix="/check-in"' in router


def test_checkin_notifies_customer_with_original_schedule() -> None:
    route = _source("apps/api/app/api/v1/routes/checkin.py")

    assert "Seu check-in foi registrado." in route
    assert "Data/Horário:" in route
    assert "starts_at_br" in route
    assert "customer_phone" in route
    assert 'template_key="appointment_checked_in"' in route
    assert 'template_key="appointment_checked_in_email"' in route
    assert '"appointment.checked_in"' in route
    assert "completed_by_checkin" in route
