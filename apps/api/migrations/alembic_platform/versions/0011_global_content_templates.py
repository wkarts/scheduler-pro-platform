import json

import sqlalchemy as sa
from alembic import op

revision = "platform_0011_global_templates"
down_revision = "platform_0010_admin_2fa"
branch_labels = None
depends_on = None


STUDIO_BEATRIZ_LANDING = {
    "version": 2,
    "title": "Studio Beatriz Nails",
    "global_styles": {
        "primary": "#b5864e",
        "secondary": "#2b2527",
        "accent": "#d6b379",
        "background": "#f8f6f3",
        "text": "#332d2f",
        "heading_font": "Georgia",
        "body_font": "Inter",
        "radius": 26,
        "button_style": "pill",
        "max_width": 1180,
    },
    "seo": {
        "title": "Studio Beatriz Nails | Agendamento",
        "description": "Studio de beleza com atendimento marcado e agendamento online.",
        "share_image": "",
        "canonical_url": "",
    },
    "blocks": [
        {
            "id": "studio-beatriz-hero-v1",
            "type": "hero",
            "props": {
                "eyebrow": "Studio de beleza • hora marcada",
                "title": "Seu momento. Seu detalhe.",
                "text": "Um espaço para cuidar de você com calma, atenção e horário reservado.",
                "cta": "Escolher meu horário",
                "image": "",
            },
            "style": {"minHeight": "720px"},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {"minHeight": "auto"}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
        {
            "id": "studio-beatriz-intro-v1",
            "type": "text",
            "props": {
                "title": "Cuidado que cabe no seu tempo",
                "text": "Apresente o Studio, sua proposta de atendimento e os diferenciais da experiência.",
            },
            "style": {},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
        {
            "id": "studio-beatriz-services-v1",
            "type": "services",
            "props": {"title": "Experiências do Studio", "subtitle": "Escolha seu atendimento", "show_prices": True},
            "style": {},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
        {
            "id": "studio-beatriz-experience-v1",
            "type": "cards",
            "props": {
                "title": "Uma experiência pensada nos detalhes",
                "items": [
                    {"title": "Hora marcada", "text": "Organize sua rotina escolhendo um horário disponível."},
                    {"title": "Atendimento cuidadoso", "text": "Valorize a experiência e a atenção em cada atendimento."},
                    {"title": "Contato conectado", "text": "Confirmações e orientações pelos canais configurados."},
                ],
            },
            "style": {},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
        {
            "id": "studio-beatriz-hours-v1",
            "type": "business_hours",
            "props": {"title": "Horários de atendimento"},
            "style": {},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
        {
            "id": "studio-beatriz-booking-v1",
            "type": "booking",
            "props": {"title": "Escolha seu horário", "subtitle": "Serviço, data, horário e seus dados em poucos passos."},
            "style": {},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
        {
            "id": "studio-beatriz-footer-v1",
            "type": "footer",
            "props": {"text": "Studio Beatriz Nails · atendimento com hora marcada."},
            "style": {},
            "responsive": {"desktop": {}, "tablet": {}, "mobile": {}, "hidden": {"desktop": False, "tablet": False, "mobile": False}},
        },
    ],
    "template_meta": {
        "source": "studio-beatriz-nails-scheduler-pro-nova-imagem",
        "family": "studio-neils",
        "official": True,
        "surface": "LANDING",
    },
}

STUDIO_BEATRIZ_BOOKING = {
    "version": 1,
    "surface": "BOOKING",
    "global_styles": {
        "primary": "#b5864e",
        "secondary": "#2b2527",
        "accent": "#d6b379",
        "background": "#f8f6f3",
        "surface": "#ffffff",
        "text": "#332d2f",
        "muted": "#776e71",
        "radius": 26,
    },
    "layout": {
        "hero": True,
        "service_selector": "cards",
        "professional_selector": "cards",
        "calendar": "month_days",
        "time_selector": "chips",
        "customer_form": "compact",
        "mobile_sticky_action": True,
    },
    "copy": {
        "eyebrow": "Agendamento online",
        "title": "Escolha seu horário",
        "subtitle": "Selecione o atendimento e encontre a melhor disponibilidade.",
        "success": "Seu horário foi reservado. Confira o canal de confirmação configurado.",
    },
    "template_meta": {"family": "studio-neils", "official": True, "surface": "BOOKING"},
}


def upgrade() -> None:
    op.execute(
        """
        create table if not exists global_content_templates (
          id uuid primary key default uuid_generate_v4(),
          surface varchar(24) not null,
          key varchar(120) not null,
          name varchar(180) not null,
          description text,
          segment varchar(80),
          status varchar(24) not null default 'DRAFT',
          scope varchar(24) not null default 'GLOBAL',
          default_for_new_tenants boolean not null default false,
          exclusive_tenant_id uuid references tenants(id) on delete set null,
          selected_tenant_ids jsonb not null default '[]'::jsonb,
          latest_version integer not null default 0,
          created_by varchar(180),
          updated_by varchar(180),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          constraint uq_global_content_template_surface_key unique(surface, key),
          constraint ck_global_content_template_surface check(surface in ('LANDING','BOOKING')),
          constraint ck_global_content_template_status check(status in ('DRAFT','PUBLISHED','INACTIVE')),
          constraint ck_global_content_template_scope check(scope in ('GLOBAL','SELECTED','EXCLUSIVE','INTERNAL'))
        )
        """
    )
    op.execute(
        """
        create table if not exists global_content_template_versions (
          id uuid primary key default uuid_generate_v4(),
          template_id uuid not null references global_content_templates(id) on delete cascade,
          version_number integer not null,
          content jsonb not null,
          changelog text,
          published boolean not null default false,
          created_by varchar(180),
          created_at timestamptz not null default now(),
          constraint uq_global_content_template_version unique(template_id, version_number),
          constraint ck_global_content_template_version_positive check(version_number > 0)
        )
        """
    )
    op.execute("create index if not exists ix_global_content_templates_surface_status on global_content_templates(surface, status)")
    op.execute("create index if not exists ix_global_content_template_versions_template on global_content_template_versions(template_id, version_number desc)")

    op.execute(
        """
        insert into platform_permissions(key, description, group_name) values
          ('templates.manage', 'Criar, versionar e publicar modelos globais de Landing Page e Página de Agendamento', 'templates'),
          ('tenant.support.manage', 'Configurar recursos e personalizações de tenants pelo Control Plane', 'tenants')
        on conflict(key) do update set description=excluded.description, group_name=excluded.group_name
        """
    )
    for role in ("Administrador", "Operações"):
        for permission in ("templates.manage", "tenant.support.manage"):
            op.execute(
                "insert into platform_role_permissions(role_id, permission_key) "
                f"select id, '{permission}' from platform_roles where name='{role}' "
                "on conflict do nothing"
            )
    op.execute(
        "insert into platform_role_permissions(role_id, permission_key) "
        "select id, 'tenant.support.manage' from platform_roles where name='Suporte' "
        "on conflict do nothing"
    )

    op.execute(
        """
        insert into global_content_templates(
          surface,key,name,description,segment,status,scope,
          default_for_new_tenants,latest_version,created_by,updated_by
        ) values(
          'LANDING','studio-beatriz-nails','Studio Beatriz Nails',
          'Modelo oficial elegante para Studio, Nails, manicure e estética.',
          'beleza-visual','PUBLISHED','GLOBAL',false,1,'system','system'
        ) on conflict(surface,key) do nothing
        """
    )
    op.execute(
        """
        insert into global_content_templates(
          surface,key,name,description,segment,status,scope,
          default_for_new_tenants,latest_version,created_by,updated_by
        ) values(
          'BOOKING','studio-beatriz-nails','Studio Beatriz Nails — Agendamento',
          'Página de agendamento coerente com a identidade oficial Studio Beatriz Nails.',
          'beleza-visual','PUBLISHED','GLOBAL',false,1,'system','system'
        ) on conflict(surface,key) do nothing
        """
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            insert into global_content_template_versions(
              template_id,version_number,content,changelog,published,created_by
            )
            select id,1,cast(:content as jsonb),:changelog,true,'system'
            from global_content_templates
            where surface='LANDING' and key='studio-beatriz-nails'
            on conflict(template_id,version_number) do nothing
            """
        ),
        {
            "content": json.dumps(STUDIO_BEATRIZ_LANDING, ensure_ascii=False),
            "changelog": "Versão inicial baseada no layout oficial Studio Beatriz Nails.",
        },
    )
    bind.execute(
        sa.text(
            """
            insert into global_content_template_versions(
              template_id,version_number,content,changelog,published,created_by
            )
            select id,1,cast(:content as jsonb),:changelog,true,'system'
            from global_content_templates
            where surface='BOOKING' and key='studio-beatriz-nails'
            on conflict(template_id,version_number) do nothing
            """
        ),
        {
            "content": json.dumps(STUDIO_BEATRIZ_BOOKING, ensure_ascii=False),
            "changelog": "Versão inicial da página de agendamento.",
        },
    )


def downgrade() -> None:
    op.execute("delete from platform_role_permissions where permission_key in ('templates.manage','tenant.support.manage')")
    op.execute("delete from platform_permissions where key in ('templates.manage','tenant.support.manage')")
    op.execute("drop table if exists global_content_template_versions cascade")
    op.execute("drop table if exists global_content_templates cascade")
