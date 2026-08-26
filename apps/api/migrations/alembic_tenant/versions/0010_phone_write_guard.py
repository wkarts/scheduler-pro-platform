"""Canonical phone write guard for tenant databases.

Revision ID: tenant_0010_phone_guard
Revises: tenant_0009_booking_phone_2fa

This migration deliberately does NOT normalize historical rows. It only keeps
phone_normalized synchronized for new/changed writes and adds a partial unique
index for canonical customer phones produced from this point forward.
"""

from alembic import op

revision = "tenant_0010_phone_guard"
down_revision = "tenant_0009_booking_phone_2fa"
branch_labels = None
depends_on = None


NORMALIZE_FUNCTION = r"""
create or replace function scheduler_normalize_phone_write(raw_phone text)
returns text
language plpgsql
stable
as $$
declare
    digits text;
    country text := 'BR';
    country_code text := '55';
    area_code text := '';
    add_ninth boolean := true;
begin
    if raw_phone is null or btrim(raw_phone) = '' then
        return null;
    end if;

    digits := regexp_replace(raw_phone, '[^0-9]', '', 'g');
    if digits = '' then
        return null;
    end if;

    select coalesce(trim(both '"' from value::text), 'BR')
      into country
      from tenant_settings where key='phone_default_country' limit 1;
    select coalesce(trim(both '"' from value::text), '55')
      into country_code
      from tenant_settings where key='phone_country_code' limit 1;
    select coalesce(trim(both '"' from value::text), '')
      into area_code
      from tenant_settings where key='phone_default_area_code' limit 1;
    select coalesce((value #>> '{}')::boolean, true)
      into add_ninth
      from tenant_settings where key='phone_add_ninth_digit' limit 1;

    country := upper(coalesce(country, 'BR'));
    country_code := regexp_replace(coalesce(country_code, '55'), '[^0-9]', '', 'g');
    area_code := regexp_replace(coalesce(area_code, ''), '[^0-9]', '', 'g');

    if country = 'BR' and country_code = '55' then
        -- Already canonical / includes country code.
        if left(digits, 2) = '55' and length(digits) in (12, 13) then
            if length(digits) = 12 and add_ninth then
                return '55' || substr(digits, 3, 2) || '9' || substr(digits, 5);
            end if;
            return digits;
        end if;

        -- DDD + local number.
        if length(digits) = 11 then
            return '55' || digits;
        end if;
        if length(digits) = 10 then
            if add_ninth then
                return '55' || substr(digits, 1, 2) || '9' || substr(digits, 3);
            end if;
            return '55' || digits;
        end if;

        -- Local number; only normalize when company has an explicit DDD.
        if length(digits) = 9 and length(area_code) = 2 then
            return '55' || area_code || digits;
        end if;
        if length(digits) = 8 and length(area_code) = 2 then
            if add_ninth then
                return '55' || area_code || '9' || digits;
            end if;
            return '55' || area_code || digits;
        end if;
        return null;
    end if;

    if country_code = '' then
        return null;
    end if;
    if left(digits, length(country_code)) = country_code then
        return digits;
    end if;
    if area_code <> '' then
        return country_code || area_code || digits;
    end if;
    return country_code || digits;
end;
$$;
"""


TRIGGER_FUNCTION = r"""
create or replace function scheduler_sync_phone_normalized()
returns trigger
language plpgsql
as $$
begin
    if tg_table_name = 'customers' then
        if tg_op = 'INSERT' or new.phone is distinct from old.phone or new.phone_normalized is null then
            new.phone_normalized := scheduler_normalize_phone_write(new.phone);
            if new.phone_normalized is not null then
                new.phone := new.phone_normalized;
            end if;
        end if;
    elsif tg_table_name = 'professionals' then
        if tg_op = 'INSERT' or new.phone is distinct from old.phone or new.phone_normalized is null then
            new.phone_normalized := scheduler_normalize_phone_write(new.phone);
            if new.phone_normalized is not null then
                new.phone := new.phone_normalized;
            end if;
        end if;
    end if;
    return new;
end;
$$;
"""


def upgrade() -> None:
    op.execute(NORMALIZE_FUNCTION)
    op.execute(TRIGGER_FUNCTION)
    op.execute("drop trigger if exists trg_customers_phone_normalized on customers")
    op.execute(
        """
        create trigger trg_customers_phone_normalized
        before insert or update of phone, phone_normalized on customers
        for each row execute function scheduler_sync_phone_normalized()
        """
    )
    op.execute("drop trigger if exists trg_professionals_phone_normalized on professionals")
    op.execute(
        """
        create trigger trg_professionals_phone_normalized
        before insert or update of phone, phone_normalized on professionals
        for each row execute function scheduler_sync_phone_normalized()
        """
    )
    op.execute(
        """
        create unique index if not exists uq_customers_phone_normalized
        on customers(phone_normalized)
        where phone_normalized is not null
        """
    )


def downgrade() -> None:
    op.execute("drop index if exists uq_customers_phone_normalized")
    op.execute("drop trigger if exists trg_professionals_phone_normalized on professionals")
    op.execute("drop trigger if exists trg_customers_phone_normalized on customers")
    op.execute("drop function if exists scheduler_sync_phone_normalized()")
    op.execute("drop function if exists scheduler_normalize_phone_write(text)")
