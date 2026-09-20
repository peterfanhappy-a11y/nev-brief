import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "ci" / "verify_vercel_project.py"
EXPECTED_PROJECT_ID = "prj_Ofzps1SPtNfdqm7JLzkTu0gybtET"
EXPECTED_PROJECT_NAME = "peterfanhappy-a11y-nev-brief"


def _run(project_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [sys.executable, str(SCRIPT), str(project_file)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_accepts_canonical_vercel_project(tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text(
        json.dumps(
            {
                "projectId": EXPECTED_PROJECT_ID,
                "projectName": EXPECTED_PROJECT_NAME,
            }
        ),
        encoding="utf-8",
    )

    result = _run(project_file)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        f"ok: Vercel target {EXPECTED_PROJECT_NAME} ({EXPECTED_PROJECT_ID})"
    )


def test_rejects_legacy_vercel_project(tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text(
        json.dumps(
            {
                "projectId": "prj_6kNhrJiQvjdBUum1DFBjAndlHAlW",
                "projectName": "nev-brief",
            }
        ),
        encoding="utf-8",
    )

    result = _run(project_file)

    assert result.returncode == 1
    assert result.stderr.strip() == (
        "error: refusing Vercel target nev-brief "
        "(prj_6kNhrJiQvjdBUum1DFBjAndlHAlW); expected "
        f"{EXPECTED_PROJECT_NAME} ({EXPECTED_PROJECT_ID})"
    )


def test_rejects_correct_id_with_wrong_name(tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text(
        json.dumps(
            {
                "projectId": EXPECTED_PROJECT_ID,
                "projectName": "wrong-project-name",
            }
        ),
        encoding="utf-8",
    )

    result = _run(project_file)

    assert result.returncode == 1


def test_rejects_correct_name_with_wrong_id(tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text(
        json.dumps(
            {
                "projectId": "prj_wrong",
                "projectName": EXPECTED_PROJECT_NAME,
            }
        ),
        encoding="utf-8",
    )

    result = _run(project_file)

    assert result.returncode == 1


def test_rejects_missing_vercel_project_link(tmp_path: Path) -> None:
    project_file = tmp_path / "missing.json"

    result = _run(project_file)

    assert result.returncode == 1
    assert result.stderr.strip() == (
        f"error: Vercel project link not found: {project_file}"
    )


def test_rejects_invalid_vercel_project_link(tmp_path: Path) -> None:
    project_file = tmp_path / "project.json"
    project_file.write_text("not-json\n", encoding="utf-8")

    result = _run(project_file)

    assert result.returncode == 1
    assert result.stderr.strip() == (
        f"error: invalid Vercel project link JSON: {project_file}"
    )
