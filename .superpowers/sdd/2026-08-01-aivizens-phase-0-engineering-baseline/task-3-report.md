# Task 3 Report — Passing lint and type-check baseline

## Status

DONE_WITH_CONCERNS. The required `make lint` and `make typecheck` commands both exit 0. Strict mypy remains enabled, Ruff runtime security/error rule families remain enabled, and default Python tests pass with all opt-in markers still excluded.

## RED baseline

All Python commands used:

```text
UV_CACHE_DIR=/private/tmp/nev-brief-uv-cache
UV_PROJECT_ENVIRONMENT=/Users/jack/Documents/codex/nev-brief/.venv
UV_NO_SYNC=1
```

Commands and results before changes:

```text
uv run ruff check packages/
exit 1 — 226 errors; 65 initially reported fixable (Ruff safe fix ultimately fixed 88 after scoped config changes).

uv run mypy packages/ai-brief packages/shared
exit 1 — 111 errors in 29 files; 56 source files checked.

npm --workspace @nev/web run lint
exit 0 — 0 errors, 2 existing @next/next/no-img-element warnings.

npm --workspace @nev/web run typecheck
exit 0 — tsc --noEmit passed.
```

## Changes

### Configuration and command surface

- `pyproject.toml`
  - Moved `ANN` and `S101` ignores to Python test files only.
  - Added the brief-authorized `condenser.py` `E501` exception for long prompt text.
  - Kept strict mypy; added worktree-local paths for the owned crawler/pipeline packages.
  - Added narrowly scoped missing-stub overrides for third-party `feedparser` and `yaml` only.
- `Makefile`
  - `make lint`: Ruff over `packages/`, then the `@nev/web` lint script.
  - `make typecheck`: strict scoped mypy, then the `@nev/web` TypeScript script.
- `.github/workflows/lint.yml`
  - CI installs both dependency sets and invokes the same Make targets used locally.
- `packages/web/package.json` already contained the exact `lint` and `typecheck` scripts required by the brief, so no no-op edit was made.
- Added `py.typed` markers to the owned `nev_crawler` and `nev_pipeline` packages.

### Ruff cleanup

- Ran `uv run ruff check packages/ --fix`; reviewed all runtime-file changes.
- Applied safe import ordering, unused-import removal, `datetime.UTC` modernization, and line wrapping.
- Added return/argument annotations without changing execution.
- Preserved legacy `str, Enum` behavior with scoped `UP042` comments instead of converting to `StrEnum`.
- Preserved intentional plain-text Jinja rendering with line-scoped `S701` comments.
- Documented closed-set SQL assembly, non-cryptographic scheduling jitter, and fixed subprocess command tables with line-scoped security comments.
- Did not globally disable Ruff `F`, `B`, `S`, or `BLE` rules.

### Strict mypy cleanup

- Added precise generic arguments, callback signatures, test-fixture annotations, TypedDicts, and no-op casts at dynamic library boundaries.
- Narrowed nullable test results with real assertions.
- Typed IMAP/MIME, feedparser, selectolax, Pillow, Resend, and JSON boundaries without adding or changing runtime branches.
- Removed stale `type: ignore` comments where current library types are sufficient.

## GREEN verification

Final commands and outputs:

```text
make lint
exit 0 — Ruff: All checks passed; web lint: 0 errors, 2 existing image warnings.

make typecheck
exit 0 — mypy: Success, no issues in 56 source files; tsc --noEmit passed.
```

Default tests were run with inert test-only required settings and a worktree-first `PYTHONPATH`, preventing local `.env` values from being read and ensuring imports exercised this worktree:

```text
make test-unit
exit 0 — 285 passed, 19 deselected, 68 warnings in 18.80s.
```

The 19 deselections preserve integration/network/golden/perf tests as opt-in. Warnings are existing Python 3.14 `datetime.utcnow()` deprecations and Pydantic warnings, not test failures.

An earlier default-suite attempt without inert required settings failed seven tests during settings construction; no product assertion failed. The protected rerun above is the authoritative result.

## Self-review

- `git diff --check` is clean.
- Reviewed Ruff's runtime-file diff after the safe fixer and reviewed the final runtime/config diff again before verification.
- All changes are annotations, casts, comments, imports, equivalent expressions, or static command/config updates; no product branch, output contract, network behavior, persistence behavior, or NEV data/code was removed.
- CI and local lint/type-check file scopes are identical because CI calls the Make targets directly.
- No `.env` values or production credentials are recorded in this report.

## Concerns

- Web lint still reports two pre-existing `<img>` optimization warnings in `components/footer.tsx` and `components/header.tsx`; lint exits 0 and changing rendering was outside this no-runtime-behavior task.
- The local shared UV environment currently runs Python 3.14 while project/tool targets remain Python 3.12; the default suite passes, with existing deprecation warnings noted above.
