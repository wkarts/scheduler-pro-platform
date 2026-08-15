create table if not exists build_requests (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  build_profile_id uuid references build_profiles(id) on delete set null,
  target varchar(40) not null,
  status varchar(32) not null default 'QUEUED',
  requested_by uuid,
  request_payload jsonb not null default '{}',
  correlation_id varchar(100) not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists ix_build_requests_tenant_status on build_requests(tenant_id, status);
create index if not exists ix_build_requests_profile on build_requests(build_profile_id);

create table if not exists build_jobs (
  id uuid primary key default uuid_generate_v4(),
  build_request_id uuid not null references build_requests(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  target varchar(40) not null,
  status varchar(32) not null default 'QUEUED',
  workflow_name varchar(120),
  workflow_run_id varchar(120),
  source_ref varchar(160),
  source_sha varchar(80),
  runner_label varchar(120),
  started_at timestamptz,
  finished_at timestamptz,
  error text,
  artifact_manifest jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(build_request_id, target)
);

create index if not exists ix_build_jobs_tenant_status on build_jobs(tenant_id, status);
create index if not exists ix_build_jobs_request on build_jobs(build_request_id);

create table if not exists build_logs (
  id uuid primary key default uuid_generate_v4(),
  build_job_id uuid not null references build_jobs(id) on delete cascade,
  sequence integer not null,
  level varchar(20) not null default 'INFO',
  message text not null,
  context jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(build_job_id, sequence)
);

create table if not exists build_artifacts (
  id uuid primary key default uuid_generate_v4(),
  build_job_id uuid not null references build_jobs(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  target varchar(40) not null,
  artifact_type varchar(40) not null,
  name varchar(180) not null,
  storage_key text,
  download_url text,
  checksum_sha256 varchar(64),
  size_bytes bigint not null default 0,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create index if not exists ix_build_artifacts_job on build_artifacts(build_job_id);
create index if not exists ix_build_artifacts_tenant on build_artifacts(tenant_id, target);

create table if not exists build_credentials (
  id uuid primary key default uuid_generate_v4(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  target varchar(40) not null,
  credential_type varchar(80) not null,
  secret_ref text not null,
  status varchar(32) not null default 'ACTIVE',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(tenant_id, target, credential_type)
);
