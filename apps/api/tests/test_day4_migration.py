from pathlib import Path


def test_day4_migration_uses_atomic_claim_leases_and_server_only_access() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "20260806084343_day4_async_investigations.sql"
    ).read_text(encoding="utf-8")

    assert "for update skip locked" in migration.lower()
    assert "lease_expires_at" in migration
    assert "investigations_one_active_per_incident_idx" in migration
    assert "alter table public.investigation_jobs enable row level security" in migration
    assert "from public, anon, authenticated" in migration
    assert "to service_role" in migration
