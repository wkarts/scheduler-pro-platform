from pathlib import Path


def test_welcome_email_json_parameters_have_explicit_postgres_types() -> None:
    source = Path(__file__).parents[1] / "app" / "services" / "provisioning_runtime.py"
    text = source.read_text(encoding="utf-8")
    assert "'welcome_email_status', cast(:status as text)" in text
    assert "'welcome_email_recipient', cast(:recipient as text)" in text


def test_runtime_rolls_back_before_persisting_failed_step() -> None:
    source = Path(__file__).parents[1] / "app" / "services" / "provisioning_runtime.py"
    text = source.read_text(encoding="utf-8")
    rollback = text.index("await self.session.rollback()", text.index("except Exception as exc"))
    failed = text.index("failed_step.status = ProvisioningStepStatus.failed.value", rollback)
    assert rollback < failed


def test_retry_recovers_running_as_well_as_failed_steps() -> None:
    source = Path(__file__).parents[1] / "app" / "api" / "v1" / "routes" / "platform.py"
    text = source.read_text(encoding="utf-8")
    assert "status <> 'completed'" in text
