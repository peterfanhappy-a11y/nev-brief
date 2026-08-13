import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ci" / "list_postgres_test_migrations.py"
MIGRATIONS_DIR = PROJECT_ROOT / "infra" / "supabase" / "migrations"
ALL_MIGRATIONS = PROJECT_ROOT / "infra" / "supabase" / "all_migrations.sql"


def test_selects_all_stock_postgres_migrations_and_excludes_supabase_storage() -> None:
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, str(SCRIPT)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "infra/supabase/migrations/0001_subscribers_and_preferences.sql",
        "infra/supabase/migrations/0002_sources_and_articles.sql",
        "infra/supabase/migrations/0003_briefs_deliveries_sales.sql",
        "infra/supabase/migrations/0004_rls_policies.sql",
        "infra/supabase/migrations/0005_sources_name_unique.sql",
        "infra/supabase/migrations/0006_sources_type_add_nextjs_json.sql",
        "infra/supabase/migrations/0007_articles_processed_simhash_unique.sql",
        "infra/supabase/migrations/0008_ai_subscribers.sql",
        "infra/supabase/migrations/0009_ai_pipeline.sql",
        "infra/supabase/migrations/0011_ai_subscription_confirmation.sql",
        "infra/supabase/migrations/0012_ai_brief_workflow.sql",
        "infra/supabase/migrations/0013_ai_digest_runs.sql",
    ]


def test_fails_when_declared_supabase_only_migration_is_missing(tmp_path: Path) -> None:
    (tmp_path / "0001_stock_postgres.sql").write_text("select 1;\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, str(SCRIPT), str(tmp_path)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert result.stderr.strip() == (
        "error: declared Supabase-only migration is missing: "
        "0010_ai_brief_images_bucket.sql"
    )


def test_all_migrations_suffix_matches_0006_through_0013_in_order() -> None:
    migration_names = [
        "0006_sources_type_add_nextjs_json.sql",
        "0007_articles_processed_simhash_unique.sql",
        "0008_ai_subscribers.sql",
        "0009_ai_pipeline.sql",
        "0010_ai_brief_images_bucket.sql",
        "0011_ai_subscription_confirmation.sql",
        "0012_ai_brief_workflow.sql",
        "0013_ai_digest_runs.sql",
    ]
    missing = [
        name for name in migration_names if not (MIGRATIONS_DIR / name).is_file()
    ]
    assert not missing, f"missing independent migrations: {missing}"

    expected_suffix = "".join(
        (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
        for name in migration_names
    )
    assert ALL_MIGRATIONS.read_text(encoding="utf-8").endswith(expected_suffix)
