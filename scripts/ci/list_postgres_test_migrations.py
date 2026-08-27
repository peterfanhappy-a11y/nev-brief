#!/usr/bin/env python3
"""List production migrations that can run in stock-Postgres integration CI."""

import sys
from pathlib import Path

SUPABASE_ONLY_MIGRATION = "0010_ai_brief_images_bucket.sql"


def postgres_test_migrations(migrations_dir: Path) -> list[Path]:
    """Return every SQL migration except the Supabase Storage-only migration."""
    return sorted(
        path
        for path in migrations_dir.glob("*.sql")
        if path.name != SUPABASE_ONLY_MIGRATION
    )


def main() -> int:
    migrations_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("infra/supabase/migrations")
    if not (migrations_dir / SUPABASE_ONLY_MIGRATION).is_file():
        print(
            f"error: declared Supabase-only migration is missing: {SUPABASE_ONLY_MIGRATION}",
            file=sys.stderr,
        )
        return 1
    for migration in postgres_test_migrations(migrations_dir):
        print(migration)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
