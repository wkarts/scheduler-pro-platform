-- Somente leitura. Executar com conta de monitoramento/admin.
-- Não lista textos de consultas, senhas ou tokens.
SELECT version();
SELECT name, setting, unit FROM pg_settings
WHERE name IN ('max_connections','superuser_reserved_connections','reserved_connections',
               'statement_timeout','lock_timeout','idle_in_transaction_session_timeout');
SELECT datname, usename, application_name, client_addr, state, count(*) AS connections
FROM pg_stat_activity WHERE backend_type='client backend'
GROUP BY datname, usename, application_name, client_addr, state
ORDER BY connections DESC;
SELECT count(*) FILTER (WHERE backend_type='client backend') AS client_connections,
       current_setting('max_connections')::int AS max_connections,
       count(*) FILTER (WHERE state LIKE 'idle in transaction%') AS idle_in_transaction
FROM pg_stat_activity;
SELECT pid, datname, usename, application_name, state,
       clock_timestamp()-xact_start AS transaction_age,
       clock_timestamp()-state_change AS state_age,
       wait_event_type, wait_event
FROM pg_stat_activity
WHERE backend_type='client backend' AND state LIKE 'idle in transaction%'
ORDER BY xact_start NULLS LAST;
