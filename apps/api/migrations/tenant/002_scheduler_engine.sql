create extension if not exists btree_gist;

create table if not exists business_hours (
  id uuid primary key default uuid_generate_v4(),
  professional_id uuid references professionals(id) on delete cascade,
  day_of_week integer not null check (day_of_week between 0 and 6),
  opens_at time not null,
  closes_at time not null,
  is_open boolean not null default true,
  created_at timestamptz not null default now(),
  constraint ck_business_hours_interval check (closes_at > opens_at)
);

create index if not exists ix_business_hours_professional_day on business_hours(professional_id, day_of_week);

create table if not exists blocked_periods (
  id uuid primary key default uuid_generate_v4(),
  professional_id uuid references professionals(id) on delete cascade,
  starts_at timestamptz not null,
  ends_at timestamptz not null,
  reason text,
  created_at timestamptz not null default now(),
  constraint ck_blocked_period_interval check (ends_at > starts_at)
);

create index if not exists ix_blocked_periods_range on blocked_periods using gist (tstzrange(starts_at, ends_at, '[)'));

create table if not exists appointment_status_history (
  id uuid primary key default uuid_generate_v4(),
  appointment_id uuid not null references appointments(id) on delete cascade,
  status varchar(32) not null,
  reason text,
  created_at timestamptz not null default now()
);

create table if not exists appointment_notes (
  id uuid primary key default uuid_generate_v4(),
  appointment_id uuid not null references appointments(id) on delete cascade,
  note text not null,
  created_at timestamptz not null default now()
);

create table if not exists notification_templates (
  id uuid primary key default uuid_generate_v4(),
  key varchar(120) not null unique,
  channel varchar(32) not null,
  body text not null,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists notification_jobs (
  id uuid primary key default uuid_generate_v4(),
  appointment_id uuid references appointments(id) on delete cascade,
  channel varchar(32) not null,
  recipient varchar(180) not null,
  template_key varchar(120) not null,
  payload jsonb not null default '{}'::jsonb,
  scheduled_at timestamptz not null default now(),
  sent_at timestamptz,
  status varchar(32) not null default 'PENDING',
  error text,
  created_at timestamptz not null default now()
);

create index if not exists ix_notification_jobs_due on notification_jobs(status, scheduled_at);

create table if not exists whatsapp_integrations (
  id uuid primary key default uuid_generate_v4(),
  name varchar(120) not null default 'default',
  provider varchar(60) not null default 'evolution',
  instance_name varchar(160) not null,
  status varchar(32) not null default 'DISCONNECTED',
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(name)
);

create index if not exists ix_appointments_professional_range on appointments using gist (professional_id, tstzrange(starts_at, ends_at, '[)'));
