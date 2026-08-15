create extension if not exists "uuid-ossp";

create table if not exists customers (
  id uuid primary key default uuid_generate_v4(),
  name varchar(160) not null,
  phone varchar(40),
  email varchar(180),
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists services (
  id uuid primary key default uuid_generate_v4(),
  name varchar(160) not null,
  duration_minutes integer not null default 30,
  price numeric(12,2),
  active varchar(8) not null default 'true'
);

create table if not exists professionals (
  id uuid primary key default uuid_generate_v4(),
  name varchar(160) not null,
  email varchar(180),
  phone varchar(40)
);

create table if not exists appointments (
  id uuid primary key default uuid_generate_v4(),
  customer_id uuid not null references customers(id),
  service_id uuid not null references services(id),
  professional_id uuid not null references professionals(id),
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  status varchar(32) not null default 'PENDING',
  source varchar(32) not null default 'web',
  created_at timestamptz not null default now(),
  constraint ck_appointment_interval check (ends_at > starts_at),
  constraint uq_appointment_professional_slot unique (professional_id, starts_at, ends_at)
);

create table if not exists landing_pages (
  id uuid primary key default uuid_generate_v4(),
  slug varchar(120) not null unique,
  status varchar(32) not null default 'DRAFT',
  current_version_id uuid
);

create table if not exists landing_page_versions (
  id uuid primary key default uuid_generate_v4(),
  landing_page_id uuid not null references landing_pages(id) on delete cascade,
  version_number integer not null,
  content jsonb not null,
  created_by uuid,
  created_at timestamptz not null default now(),
  unique(landing_page_id, version_number)
);

create table if not exists whatsapp_events (
  id uuid primary key default uuid_generate_v4(),
  provider_event_id varchar(180) not null unique,
  integration_key varchar(120) not null,
  payload jsonb not null,
  received_at timestamptz not null default now()
);

create table if not exists outbox_events (
  id uuid primary key default uuid_generate_v4(),
  event_name varchar(120) not null,
  aggregate_id varchar(120) not null,
  payload jsonb not null,
  status varchar(32) not null default 'pending',
  created_at timestamptz not null default now()
);
