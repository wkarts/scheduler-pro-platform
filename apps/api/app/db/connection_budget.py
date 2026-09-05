"""Read-only connection capacity, excluding background PostgreSQL workers."""
from typing import Any

CAPACITY_SQL = """
select
    current_setting('max_connections')::int as maximum,
    current_setting('superuser_reserved_connections')::int as superuser_reserved,
    coalesce(nullif(current_setting('reserved_connections', true), ''), '0')::int as reserved,
    count(*) filter (where backend_type='client backend')::int as used,
    count(*) filter (where backend_type='client backend' and state='active')::int as active,
    count(*) filter (where backend_type='client backend' and state='idle')::int as idle,
    count(*) filter (where backend_type='client backend'
        and state like 'idle in transaction%')::int as idle_in_transaction
from pg_stat_activity
"""


def capacity_snapshot(row: Any, *, warning: int = 75, critical: int = 90) -> dict[str, Any]:
    maximum = int(row["maximum"])
    reserved = int(row["superuser_reserved"]) + int(row["reserved"])
    usable = max(0, maximum - reserved)
    used = int(row["used"])
    percentage = round(used * 100 / usable, 2) if usable else 100.0
    return {
        "maximum": maximum, "reserved_slots": reserved, "ordinary_limit": usable,
        "used": used, "free_ordinary_slots": max(0, usable - used),
        "percent_of_ordinary_capacity": percentage,
        "active": int(row["active"]), "idle": int(row["idle"]),
        "idle_in_transaction": int(row["idle_in_transaction"]),
        "status": "critical" if percentage >= critical else "warning" if percentage >= warning else "ok",
    }
