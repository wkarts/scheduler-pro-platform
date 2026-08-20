from alembic import op

revision = "platform_0009_public_booking"
down_revision = "platform_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Recurso novo e opt-in: tenants existentes e novos começam com a agenda
    # pública bloqueada até liberação explícita pelo Control Plane.
    op.execute(
        """
        insert into tenant_capabilities(tenant_id, capability_key, enabled, config)
        select id, 'public_booking', false, '{}'::jsonb
        from tenants
        on conflict(tenant_id, capability_key) do nothing
        """
    )

    # O trigger legado cria as capabilities centrais. Preservamos o comportamento
    # existente e acrescentamos apenas o novo módulo como bloqueado, sem alterar
    # as liberações atuais dos demais recursos.
    op.execute(
        """
        create or replace function scheduler_seed_public_booking_capability()
        returns trigger language plpgsql as $$
        begin
          insert into tenant_capabilities(tenant_id, capability_key, enabled, config)
          values(new.id, 'public_booking', false, '{}'::jsonb)
          on conflict do nothing;
          return new;
        end;
        $$
        """
    )
    op.execute("drop trigger if exists trg_seed_public_booking_capability on tenants")
    op.execute(
        "create trigger trg_seed_public_booking_capability "
        "after insert on tenants for each row "
        "execute function scheduler_seed_public_booking_capability()"
    )


def downgrade() -> None:
    op.execute("drop trigger if exists trg_seed_public_booking_capability on tenants")
    op.execute("drop function if exists scheduler_seed_public_booking_capability()")
    op.execute("delete from tenant_capabilities where capability_key='public_booking'")
