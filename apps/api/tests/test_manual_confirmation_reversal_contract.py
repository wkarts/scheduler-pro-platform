from pathlib import Path


def _root() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "apps" / "web").is_dir() and (parent / "apps" / "api").is_dir():
            return parent
    return None


def _read(path: str) -> str:
    root = _root()
    if root is None:
        import pytest

        pytest.skip("Fontes do monorepo não estão presentes nesta imagem.")
    return (root / path).read_text(encoding="utf-8")


def test_manual_confirmation_isolated_from_existing_confirmation_flow() -> None:
    route = _read("apps/api/app/api/v1/routes/checkin.py")
    center = _read("apps/web/src/TenantCheckInCenter.vue")
    assert '@router.post("/{appointment_id}/confirm")' in route
    assert "MANUAL_CONFIRM_REASON_PREFIX" in route
    assert "CHECKIN_CENTER_MANUAL_CONFIRM previous_status=" in route
    assert '@router.get("/{appointment_id}/undo-state")' in route
    assert "async function confirmManual" in center
    assert "title:'Confirmar atendimento'" in center
    assert "`/check-in/${item.id}/confirm`" in center
    assert "`/check-in/${item.id}/undo-state`" in center
    assert '@click="confirmManual(item)"' in center


def test_manual_confirmation_uses_same_grace_and_contextual_cancel() -> None:
    route = _read("apps/api/app/api/v1/routes/checkin.py")
    dispatcher = _read("apps/api/app/services/notification_dispatcher.py")
    center = _read("apps/web/src/TenantCheckInCenter.vue")
    assert "MANUAL_CONFIRM_NOTIFICATION_KEYS" in route
    assert "appointment_checkin_center_confirmed" in dispatcher
    assert "appointment_checkin_center_confirmed_email" in dispatcher
    assert "OPERATIONAL_TEMPLATE_KEYS" in dispatcher
    assert "resolveUndoState" in center
    assert "resolveBulkUndoPlan" in center
    assert "Confirmar selecionados" in center
    assert "Cancelar / desfazer em lote" in center
    assert "notificationDelay.value" in center
