from app.services.notification_service import NotificationService


def test_conditional_service_line_is_removed_when_service_absent() -> None:
    body = (
        "Olá, {{customer_name}}!\n"
        "{{#if service_name}}Serviço: {{service_name}}\n{{/if}}"
        "Profissional: {{professional_name}}"
    )
    rendered = NotificationService._render(
        body,
        {
            "customer_name": "João",
            "service_name": None,
            "professional_name": "Carlos",
        },
    )
    assert "Serviço:" not in rendered
    assert "null" not in rendered.lower()
    assert "Profissional: Carlos" in rendered


def test_conditional_service_line_is_rendered_when_service_exists() -> None:
    body = (
        "Olá, {{customer_name}}!\n"
        "{{#if service_name}}Serviço: {{service_name}}\n{{/if}}"
        "Profissional: {{professional_name}}"
    )
    rendered = NotificationService._render(
        body,
        {
            "customer_name": "João",
            "service_name": "Corte",
            "professional_name": "Carlos",
        },
    )
    assert "Serviço: Corte" in rendered
    assert "Profissional: Carlos" in rendered


def test_legacy_service_line_does_not_leave_empty_label() -> None:
    rendered = NotificationService._render(
        "Serviço: {{service_name}}\nProfissional: {{professional_name}}",
        {"service_name": "", "professional_name": "Carlos"},
    )
    assert rendered == "Profissional: Carlos"
