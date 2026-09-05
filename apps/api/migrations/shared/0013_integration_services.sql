-- Versioned schema shared by independent platform/tenant databases.
-- Do not mutate after release; evolve using a new migration.
create table service_integration_sweep (
  id integer primary key check(id=1),
  last_tenant_id uuid,
  next_run_at timestamptz not null default now()
);
insert into service_integration_sweep(id) values(1);
create table service_api_tokens (
  id uuid primary key default uuid_generate_v4(),
  owner_id uuid not null,
  name varchar(100) not null,
  token_hash char(64) not null unique,
  prefix varchar(32) not null,
  scopes jsonb not null check(jsonb_typeof(scopes)='array'),
  roles jsonb not null default '[]'::jsonb check(jsonb_typeof(roles)='array'),
  tenant_ids jsonb not null default '[]'::jsonb check(jsonb_typeof(tenant_ids)='array'),
  global_scope boolean not null default false,
  permissions jsonb not null check(jsonb_typeof(permissions)='array'),
  rate_limit integer not null default 120 check(rate_limit between 1 and 1000),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  last_used_at timestamptz,
  revoked_at timestamptz
);
create index ix_service_api_tokens_owner on service_api_tokens(owner_id);
create table service_api_usage (
  token_id uuid primary key references service_api_tokens(id) on delete cascade,
  window_start timestamptz not null,
  requests integer not null
);
create table service_api_requests (
  id uuid primary key default uuid_generate_v4(),
  actor_key varchar(80) not null,
  key_hash char(64) not null,
  fingerprint char(64) not null,
  authorization_snapshot jsonb not null default '{}'::jsonb,
  method varchar(8) not null,
  path varchar(512) not null,
  state varchar(32) not null default 'processing'
    check(state in ('processing','completed','unknown','response_expired','resolved')),
  response_status integer,
  response_sealed text,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  resolution_note varchar(500),
  unique(actor_key,key_hash)
);
create index ix_service_api_requests_created on service_api_requests(created_at);
create index ix_service_api_requests_actor_created on service_api_requests(actor_key,created_at desc);
create index ix_service_api_requests_pending on service_api_requests(actor_key)
  where state in ('processing','unknown');
create table service_webhook_endpoints (
  id uuid primary key default uuid_generate_v4(),
  name varchar(100) not null,
  url varchar(2048) not null,
  events jsonb not null check(jsonb_typeof(events)='array'),
  secret_ref text not null,
  authorization_ref text,
  active boolean not null default true,
  created_by uuid not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);
create table service_webhook_events (
  id uuid primary key default uuid_generate_v4(),
  event_type varchar(100) not null,
  payload jsonb not null,
  created_at timestamptz not null default now()
);
create table service_webhook_deliveries (
  id uuid primary key default uuid_generate_v4(),
  endpoint_id uuid not null references service_webhook_endpoints(id) on delete cascade,
  event_id uuid not null references service_webhook_events(id) on delete cascade,
  state varchar(16) not null default 'pending'
    check(state in ('pending','sending','delivered','failed','cancelled')),
  attempts integer not null default 0,
  cycle_attempts integer not null default 0,
  available_at timestamptz not null default now(),
  lease_id uuid,
  lease_until timestamptz,
  http_status integer,
  last_error varchar(160),
  created_at timestamptz not null default now(),
  delivered_at timestamptz,
  unique(endpoint_id,event_id)
);
create index ix_service_webhook_due on service_webhook_deliveries(available_at)
  where state in ('pending','sending');
create table service_webhook_attempts (
  id uuid primary key,
  delivery_id uuid not null references service_webhook_deliveries(id) on delete cascade,
  attempt integer not null,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  http_status integer,
  error varchar(160)
);
create index ix_service_webhook_attempts_delivery on service_webhook_attempts(delivery_id);
create table service_integration_audit (
  id uuid primary key default uuid_generate_v4(),
  actor_id uuid not null,
  action varchar(80) not null,
  resource_id uuid not null,
  created_at timestamptz not null default now()
);
create index ix_service_integration_audit_created on service_integration_audit(created_at desc);
create or replace function service_capture_webhook() returns trigger
language plpgsql as $$
declare
  item jsonb;
  previous jsonb := '{}'::jsonb;
  kind text;
  event_types text[];
  event_key uuid;
  payload_data jsonb;
begin
  if TG_OP = 'DELETE' then item := to_jsonb(OLD);
  else item := to_jsonb(NEW); end if;
  if TG_OP = 'UPDATE' then
    previous := to_jsonb(OLD);
    if (item - 'updated_at') is not distinct from (previous - 'updated_at') then
      return NEW;
    end if;
  end if;
  kind := TG_ARGV[0] || '.' || case TG_OP
    when 'INSERT' then 'created' when 'DELETE' then 'deleted' else 'updated' end;
  event_types := array[kind];
  if TG_ARGV[0] = 'appointment' and TG_OP = 'UPDATE' then
    if item->>'status' is distinct from previous->>'status'
       and lower(item->>'status') in ('confirmed','cancelled','checked_in','in_progress',
         'completed','no_show','rescheduled','awaiting_confirmation','pending') then
      event_types := array_append(event_types, 'appointment.' || lower(item->>'status'));
    end if;
    if (item->>'starts_at' is distinct from previous->>'starts_at'
        or item->>'ends_at' is distinct from previous->>'ends_at'
        or item->>'professional_id' is distinct from previous->>'professional_id')
        and not ('appointment.rescheduled' = any(event_types)) then
      event_types := array_append(event_types, 'appointment.rescheduled');
    end if;
  end if;
  foreach kind in array event_types loop
  if exists(select 1 from service_webhook_endpoints
            where active and deleted_at is null and (events ? kind or events ? '*')) then
    -- Explicit allowlist: never send passwords, phone numbers, notes, HTML or credentials.
    payload_data := jsonb_strip_nulls(jsonb_build_object(
      'resource', TG_ARGV[0], 'resource_id', item->>'id',
      'tenant_id', item->>'tenant_id', 'status', item->>'status',
      'previous_status', previous->>'status',
      'starts_at', item->>'starts_at', 'ends_at', item->>'ends_at',
      'customer_id', item->>'customer_id', 'service_id', item->>'service_id',
      'professional_id', item->>'professional_id'));
    insert into service_webhook_events(event_type,payload) values(kind,payload_data)
      returning id into event_key;
    insert into service_webhook_deliveries(endpoint_id,event_id)
      select id,event_key from service_webhook_endpoints
      where active and deleted_at is null and (events ? kind or events ? '*');
  end if;
  end loop;
  if TG_OP = 'DELETE' then return OLD; else return NEW; end if;
end;
$$;
