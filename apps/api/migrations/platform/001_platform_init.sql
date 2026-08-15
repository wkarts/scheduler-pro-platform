create extension if not exists "uuid-ossp";

create table if not exists tenants (
  id uuid primary key default uuid_generate_v4(),
  name varchar(160) not null,
  slug varchar(120) not null unique,
  status varchar(32) not null default 'PENDING',
  timezone varchar(64) not null default 'America/Bahia',
  settings jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists tenant_databases (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null unique references tenants(id) on delete cascade,
  database_name varchar(128) not null unique,
  database_user varchar(128) not null unique,
  password_ref text not null
);

create table if not exists tenant_storage (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null unique references tenants(id) on delete cascade,
  bucket varchar(160) not null unique
);

create table if not exists domains (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  hostname varchar(255) not null unique,
  is_primary boolean not null default false,
  is_temporary boolean not null default true,
  status varchar(32) not null default 'PENDING',
  validation jsonb not null default '{}'
);

create table if not exists provisioning_jobs (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  status varchar(32) not null default 'PENDING',
  correlation_id varchar(80) not null,
  created_at timestamptz not null default now()
);

create table if not exists provisioning_steps (
  id uuid primary key default uuid_generate_v4(),
  job_id uuid not null references provisioning_jobs(id) on delete cascade,
  name varchar(80) not null,
  status varchar(32) not null default 'pending',
  error text,
  unique(job_id, name)
);

create table if not exists platform_users (
  id uuid primary key default uuid_generate_v4(),
  email varchar(180) not null unique,
  password_hash text not null,
  is_super_admin boolean not null default false
);

create table if not exists feature_flags (
  key varchar(120) primary key,
  enabled boolean not null default false,
  rules jsonb not null default '{}'
);
