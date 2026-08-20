from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_open_booking_migration_enables_btree_gist_before_uuid_exclusion() -> None:
    migration = (
        ROOT
        / "apps/api/migrations/alembic_tenant/versions/0008_open_booking_and_slot_reuse.py"
    ).read_text(encoding="utf-8").lower()

    extension = "create extension if not exists btree_gist"
    exclusion = "exclude using gist"

    assert extension in migration
    assert exclusion in migration
    assert migration.index(extension) < migration.index(exclusion)
