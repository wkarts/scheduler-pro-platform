from alembic import op

revision = "platform_0006"
down_revision = "platform_0005"
branch_labels = None
depends_on = None


OLD_DEFAULTS = {
    "primary_color": "#0f172a",
    "secondary_color": "#22d3ee",
    "accent_color": "#38bdf8",
    "background_color": "#020617",
    "text_color": "#f8fafc",
    "font_family": "Inter, ui-sans-serif, system-ui",
}

NEW_DEFAULTS = {
    "primary_color": "#2F6BFF",
    "secondary_color": "#22D3EE",
    "accent_color": "#1DAAF5",
    "background_color": "#F4F7FB",
    "text_color": "#0B1D3A",
    "font_family": "Inter, Segoe UI, Arial, sans-serif",
}


def upgrade() -> None:
    op.execute("alter table tenant_branding_profiles alter column primary_color set default '#2F6BFF'")
    op.execute("alter table tenant_branding_profiles alter column secondary_color set default '#22D3EE'")
    op.execute("alter table tenant_branding_profiles alter column accent_color set default '#1DAAF5'")
    op.execute("alter table tenant_branding_profiles alter column background_color set default '#F4F7FB'")
    op.execute("alter table tenant_branding_profiles alter column text_color set default '#0B1D3A'")
    op.execute(
        "alter table tenant_branding_profiles alter column font_family "
        "set default 'Inter, Segoe UI, Arial, sans-serif'"
    )

    op.execute(
        """
        update tenant_branding_profiles
        set primary_color = '#2F6BFF'
        where lower(primary_color) = '#0f172a'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set secondary_color = '#22D3EE'
        where lower(secondary_color) = '#22d3ee'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set accent_color = '#1DAAF5'
        where lower(accent_color) = '#38bdf8'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set background_color = '#F4F7FB'
        where lower(background_color) = '#020617'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set text_color = '#0B1D3A'
        where lower(text_color) = '#f8fafc'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set font_family = 'Inter, Segoe UI, Arial, sans-serif'
        where font_family = 'Inter, ui-sans-serif, system-ui'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set slogan = 'Agenda inteligente. Operação conectada.'
        where slogan is null or btrim(slogan) = ''
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set icon_url = '/icons/icon.svg'
        where icon_url is null or btrim(icon_url) = ''
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set favicon_url = '/favicon.svg'
        where favicon_url is null or btrim(favicon_url) = ''
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set updated_at = now()
        where lower(primary_color) = '#2f6bff'
           or lower(accent_color) = '#1daaf5'
           or icon_url = '/icons/icon.svg'
           or favicon_url = '/favicon.svg'
        """
    )


def downgrade() -> None:
    op.execute("alter table tenant_branding_profiles alter column primary_color set default '#0f172a'")
    op.execute("alter table tenant_branding_profiles alter column secondary_color set default '#22d3ee'")
    op.execute("alter table tenant_branding_profiles alter column accent_color set default '#38bdf8'")
    op.execute("alter table tenant_branding_profiles alter column background_color set default '#020617'")
    op.execute("alter table tenant_branding_profiles alter column text_color set default '#f8fafc'")
    op.execute(
        "alter table tenant_branding_profiles alter column font_family "
        "set default 'Inter, ui-sans-serif, system-ui'"
    )
    op.execute(
        """
        update tenant_branding_profiles
        set primary_color = '#0f172a'
        where lower(primary_color) = '#2f6bff'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set accent_color = '#38bdf8'
        where lower(accent_color) = '#1daaf5'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set background_color = '#020617'
        where lower(background_color) = '#f4f7fb'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set text_color = '#f8fafc'
        where lower(text_color) = '#0b1d3a'
        """
    )
    op.execute(
        """
        update tenant_branding_profiles
        set font_family = 'Inter, ui-sans-serif, system-ui'
        where font_family = 'Inter, Segoe UI, Arial, sans-serif'
        """
    )
