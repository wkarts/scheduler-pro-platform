from pathlib import Path

FILE_PATH = Path(__file__).resolve()
API_ROOT = FILE_PATH.parents[1]
ROOT = API_ROOT.parent.parent if API_ROOT.name == "api" and API_ROOT.parent.name == "apps" else API_ROOT


def test_open_booking_migration_enables_btree_gist_before_uuid_exclusion() -> None:
    migration_path = (
        ROOT
        / "apps/api/migrations/alembic_tenant/versions/0008_open_booking_and_slot_reuse.py"
    )
    if not migration_path.exists():
        migration_path = API_ROOT / "migrations/alembic_tenant/versions/0008_open_booking_and_slot_reuse.py"
    migration = migration_path.read_text(encoding="utf-8").lower()

    extension = "create extension if not exists btree_gist"
    exclusion = "exclude using gist"

    assert extension in migration
    assert exclusion in migration
    assert migration.index(extension) < migration.index(exclusion)
