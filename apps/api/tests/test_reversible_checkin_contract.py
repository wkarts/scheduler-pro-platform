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


def test_manual_confirmation_from_checkin_is_confirmed_and_reversible() -> None:
    route = _read("apps/api/app/api/v1/routes/checkin.py")
    dispatcher = _read("apps/api/app/services/notification_dispatcher.py")
    assert '@router.post("/{appointment_id}/confirm")' in route
    assert '@router.get("/{appointment_id}/undo-state")' in route
    assert "MANUAL_CONFIRMABLE_STATUSES" in route
    assert "MANUAL_CONFIRM_REASON_PREFIX" in route
    assert "CHECKIN_CENTER_MANUAL_CONFIRM previous_status=" in route
    assert "_manual_confirmation_previous_status" in route
    assert "appointment_checkin_center_confirmed" in route
    assert "appointment_checkin_center_confirmed_email" in route
    assert "appointment_checkin_center_confirmed" in dispatcher
    assert "appointment_checkin_center_confirmed_email" in dispatcher
    assert "manual_confirmation" in route
    assert "previous_status" in route


def test_client_confirmation_supersedes_old_manual_confirmation() -> None:
    route = _read("apps/api/app/api/v1/routes/checkin.py")
    # O lookup deve examinar a confirmação CONFIRMED mais recente, qualquer que seja
    # a origem. Filtrar primeiro pelo prefixo manual faria uma marca antiga sobreviver
    # indevidamente a uma confirmação posterior realizada pelo próprio cliente.
    manual_lookup = route.split(
        "async def _manual_confirmation_previous_status", 1
    )[1].split("async def _publish_realtime", 1)[0]
    assert "and status=:confirmed" in manual_lookup
    assert "and reason like :prefix" not in manual_lookup
    assert "order by created_at desc" in manual_lookup
    assert "value.startswith(MANUAL_CONFIRM_REASON_PREFIX)" in manual_lookup
    assert "confirmação mais nova passa a ser soberana" in manual_lookup


def test_operational_notifications_have_configurable_grace_window() -> None:
    parameters = _read("apps/api/app/services/booking_parameters_service.py")
    dispatcher = _read("apps/api/app/services/notification_dispatcher.py")
    assert '"checkin_notification_delay_seconds"' in parameters
    assert "notification_delay < 0 or notification_delay > 600" in parameters
    assert "OPERATIONAL_TEMPLATE_KEYS" in dispatcher
    assert "_operational_delay_seconds" in dispatcher
    assert "operational_cutoff" in dispatcher
    assert "scheduled_at <= :operational_cutoff" in dispatcher
    assert "appointment_checkin_center_confirmed" in dispatcher


def test_checkin_ui_confirms_and_uses_cancel_as_contextual_undo() -> None:
    center = _read("apps/web/src/TenantCheckInCenter.vue")
    assert "async function confirmManual" in center
    assert "title:'Confirmar atendimento'" in center
    assert "`/check-in/${item.id}/confirm`" in center
    assert "async function confirmCheckIn" in center
    assert "Confirmar Check-in" in center
    assert "async function resolveUndoState" in center
    assert "`/check-in/${item.id}/undo-state`" in center
    assert "async function cancelOne" in center
    assert "`/check-in/${item.id}/undo`" in center
    assert "checkin_notification_delay_seconds" in center
    assert "Confirmar selecionados" in center
    assert "Confirmar Check-in em lote" in center
    assert "Cancelar / desfazer em lote" in center
    assert '@click="confirmManual(item)"' in center
    assert "mobile-tab-history .sp-checkin-row .actions" in center
