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


def test_checkin_has_one_step_undo_and_pending_message_cancellation() -> None:
    route = _read("apps/api/app/api/v1/routes/checkin.py")
    assert '@router.post("/{appointment_id}/undo")' in route
    assert "AppointmentStatus.checked_in.value" in route
    assert "AppointmentStatus.in_progress.value" in route
    assert "AppointmentStatus.completed.value" in route
    assert "AppointmentStatus.cancelled.value" in route
    assert "AppointmentStatus.no_show.value" in route
    assert "status='CANCELLED'" in route
    assert "notifications_cancelled" in route
    assert "notifications_already_sent" in route


def test_operational_notifications_have_configurable_grace_window() -> None:
    parameters = _read("apps/api/app/services/booking_parameters_service.py")
    dispatcher = _read("apps/api/app/services/notification_dispatcher.py")
    assert '"checkin_notification_delay_seconds"' in parameters
    assert "notification_delay < 0 or notification_delay > 600" in parameters
    assert "OPERATIONAL_TEMPLATE_KEYS" in dispatcher
    assert "_operational_delay_seconds" in dispatcher
    assert "operational_cutoff" in dispatcher
    assert "scheduled_at <= :operational_cutoff" in dispatcher


def test_checkin_ui_confirms_and_uses_cancel_as_contextual_undo() -> None:
    center = _read("apps/web/src/TenantCheckInCenter.vue")
    assert "async function confirmCheckIn" in center
    assert "Confirmar Check-in" in center
    assert "async function cancelOne" in center
    assert "if(canUndo(item))" in center
    assert "`/check-in/${item.id}/undo`" in center
    assert "checkin_notification_delay_seconds" in center
    assert "Confirmar Check-in em lote" in center
    assert "Cancelar / desfazer em lote" in center
    assert "mobile-tab-history .sp-checkin-row .actions" in center
