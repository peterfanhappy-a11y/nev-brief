import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ci" / "list_postgres_test_migrations.py"


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
