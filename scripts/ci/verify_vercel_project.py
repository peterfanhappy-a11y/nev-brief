#!/usr/bin/env python3
"""Refuse explicit Vercel deploys from a checkout linked to the wrong project."""

import json
import sys
from pathlib import Path

EXPECTED_PROJECT_ID = "prj_Ofzps1SPtNfdqm7JLzkTu0gybtET"
EXPECTED_PROJECT_NAME = "peterfanhappy-a11y-nev-brief"


def main() -> int:
    project_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".vercel/project.json")
    if not project_file.is_file():
        print(f"error: Vercel project link not found: {project_file}", file=sys.stderr)
        return 1

    try:
        project = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print(f"error: invalid Vercel project link JSON: {project_file}", file=sys.stderr)
        return 1

    project_id = project.get("projectId")
    project_name = project.get("projectName")
    if project_id != EXPECTED_PROJECT_ID or project_name != EXPECTED_PROJECT_NAME:
        print(
            f"error: refusing Vercel target {project_name} ({project_id}); expected "
            f"{EXPECTED_PROJECT_NAME} ({EXPECTED_PROJECT_ID})",
            file=sys.stderr,
        )
        return 1

    print(f"ok: Vercel target {EXPECTED_PROJECT_NAME} ({EXPECTED_PROJECT_ID})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
