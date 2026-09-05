-- Shared only by the new platform/tenant migrations; prior migrations remain immutable.
alter table service_api_tokens alter column expires_at drop not null;
create table service_webhook_receivers (
 id uuid primary key default uuid_generate_v4(),
 name varchar(100) not null,
 created_by uuid,
 auth_mode varchar(12) not null check(auth_mode in ('hmac','bearer')),
 secret_ref text,
 secret_hash char(64) not null,
 events jsonb not null check(jsonb_typeof(events)='array'),
 active boolean not null default true,
 rate_limit integer not null default 120 check(rate_limit between 1 and 1000),
 window_start timestamptz not null default now(),
 window_requests integer not null default 0,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 last_received_at timestamptz,
 revoked_at timestamptz,
 check(auth_mode <> 'hmac' or secret_ref is not null)
);
create table service_webhook_inbox (
 id uuid primary key default uuid_generate_v4(),
 receiver_id uuid not null references service_webhook_receivers(id),
 external_id varchar(128) not null,
 event_type varchar(100) not null,
 fingerprint char(64) not null,
 payload_sealed text,
 payload_expires_at timestamptz not null,
 received_at timestamptz not null default now(),
 state varchar(20) not null default 'received' check(state in ('received','acknowledged','ignored')),
 reviewed_by uuid,
 reviewed_at timestamptz,
 unique(receiver_id,external_id)
);
create index ix_service_webhook_inbox_received on service_webhook_inbox(received_at desc,id);
create index ix_service_webhook_inbox_payload on service_webhook_inbox(payload_expires_at) where payload_sealed is not null;
