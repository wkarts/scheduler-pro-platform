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


def test_confirmation_operator_has_status_resend_and_safe_renew() -> None:
    route = _read("apps/api/app/api/v1/routes/appointment_confirmations.py")
    assert '@router.post("/statuses")' in route
    assert '@router.post("/{appointment_id}/send")' in route
    assert 'action not in {"send", "resend", "renew"}' in route
    assert "AUTO_EXPIRY_REASON_PREFIX" in route
    assert "auto_expired_cancel" in route
    assert "_ensure_slot_available" in route
    assert "ignore_appointment_id=appointment_id" in route
    assert "Prazo de confirmação renovado manualmente" in route
    assert "CONFIRMATION_MANUAL_SEND_NOT_ALLOWED" in route


def test_confirmation_resend_never_logs_link_or_token() -> None:
    route = _read("apps/api/app/api/v1/routes/appointment_confirmations.py")
    audit = route[route.index("await record_tenant_event("):]
    audit = audit[: audit.index("await session.commit()")]
    assert '"confirmation_deadline"' in audit
    assert '"expires_at"' in audit
    assert '"confirmation_url"' not in audit
    assert '"url"' not in audit
    assert '"token"' not in audit


def test_confirmation_resend_requeues_only_confirmation_messages() -> None:
    route = _read("apps/api/app/api/v1/routes/appointment_confirmations.py")
    assert "CONFIRMATION_MESSAGE_KEYS" in route
    assert "appointment_confirmation_request" in route
    assert "appointment_confirmation_resend" in route
    assert "appointment_confirmation_renewed" in route
    assert "Substituída por envio manual mais recente" in route
    assert "sent_at=null" in route
    assert "status='PENDING'" in route


def test_new_standard_message_models_are_data_only_and_non_destructive() -> None:
    migration = _read(
        "apps/api/migrations/alembic_tenant/versions/0012_confirmation_resend_models.py"
    )
    assert 'down_revision = "tenant_0011_experience_v2"' in migration
    assert "appointment_confirmation_resend" in migration
    assert "appointment_confirmation_resend_email" in migration
    assert "appointment_confirmation_renewed" in migration
    assert "appointment_confirmation_renewed_email" in migration
    assert "on conflict (key) do nothing" in migration
    assert "alter table" not in migration.lower()
    assert "create table" not in migration.lower()


def test_tenant_has_discrete_confirmation_assistant_without_touching_checkin_flow() -> None:
    app = _read("apps/web/src/App.vue")
    assistant = _read("apps/web/src/TenantConfirmationAssistant.vue")
    assert "TenantConfirmationAssistant" in app
    assert "MessageCircle" in assistant
    assert "Reenviar link" in assistant
    assert "Renovar e enviar" in assistant
    assert "Prazo de confirmação vencido" not in assistant  # label vem do backend
    assert "/appointment-confirmations/statuses" in assistant
    assert "`/appointment-confirmations/${item.id}/send`" in assistant
    assert "O Scheduler Pro verificará novamente a disponibilidade" in assistant
    assert "Links e tokens de confirmação não são exibidos" in assistant
