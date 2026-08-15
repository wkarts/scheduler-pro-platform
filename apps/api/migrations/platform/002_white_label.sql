create table if not exists tenant_branding_profiles (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null unique references tenants(id) on delete cascade,
  status varchar(32) not null default 'DRAFT',
  app_name varchar(160) not null,
  public_name varchar(160) not null,
  slogan varchar(220),
  logo_url text,
  icon_url text,
  favicon_url text,
  primary_color varchar(20) not null default '#0f172a',
  secondary_color varchar(20) not null default '#22d3ee',
  accent_color varchar(20) not null default '#38bdf8',
  background_color varchar(20) not null default '#020617',
  text_color varchar(20) not null default '#f8fafc',
  font_family varchar(120) not null default 'Inter, ui-sans-serif, system-ui',
  border_radius varchar(20) not null default '1rem',
  theme_mode varchar(20) not null default 'system',
  locale varchar(20) not null default 'pt-BR',
  timezone varchar(64) not null default 'America/Bahia',
  settings jsonb not null default '{}',
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists tenant_branding_assets (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  branding_profile_id uuid not null references tenant_branding_profiles(id) on delete cascade,
  asset_type varchar(40) not null,
  storage_key text not null,
  public_url text,
  mime_type varchar(120) not null,
  size_bytes bigint not null default 0,
  checksum_sha256 varchar(64),
  created_at timestamptz not null default now(),
  unique(branding_profile_id, asset_type, storage_key)
);

create table if not exists build_profiles (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  branding_profile_id uuid references tenant_branding_profiles(id) on delete set null,
  name varchar(160) not null,
  target varchar(40) not null,
  bundle_identifier varchar(200),
  package_name varchar(200),
  api_url text not null,
  features jsonb not null default '[]',
  config jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(tenant_id, target, name)
);

create index if not exists idx_tenant_branding_profiles_tenant on tenant_branding_profiles(tenant_id);
create index if not exists idx_tenant_branding_assets_tenant on tenant_branding_assets(tenant_id);
create index if not exists idx_build_profiles_tenant on build_profiles(tenant_id);
