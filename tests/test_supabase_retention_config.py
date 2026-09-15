from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _migration_text() -> str:
    matches = list(
        (ROOT / "supabase" / "migrations").glob(
            "*_schedule_image_retention.sql"
        )
    )
    assert len(matches) == 1
    return matches[0].read_text()


def test_edge_gateway_uses_function_level_secret():
    config = (ROOT / "supabase" / "config.toml").read_text()
    assert "[functions.cleanup-expired-images]" in config
    function_config = config.split(
        "[functions.cleanup-expired-images]", maxsplit=1
    )[1].split("\n[", maxsplit=1)[0]
    assert "verify_jwt = false" in function_config
    assert "tjdzldgccmnspanonthk" not in config
    assert "service_role" not in function_config.lower()


def test_cron_is_bounded_to_the_fixed_function_and_secret_header():
    sql = _migration_text()
    assert "create extension if not exists pg_cron" in sql.lower()
    assert "create extension if not exists pg_net" in sql.lower()
    assert "'cleanup-expired-images'" in sql
    assert "'*/15 * * * *'" in sql
    assert "/functions/v1/cleanup-expired-images" in sql
    assert "'X-Cleanup-Secret'" in sql
    assert "cleanup_cron_secret" in sql
    assert "project_url" in sql
    assert "jsonb_build_object('dry_run', false)" in sql
    assert "service_role" not in sql.lower()
    assert "storage.objects" not in sql.lower()


def test_function_uses_supported_storage_api_only():
    function_dir = (
        ROOT / "supabase" / "functions" / "cleanup-expired-images"
    )
    source = "\n".join(
        path.read_text()
        for path in function_dir.glob("*.ts")
        if not path.name.endswith(".test.ts")
    )
    assert ".storage.from(bucket).remove(paths)" in source
    assert "storage.objects" not in source.lower()
