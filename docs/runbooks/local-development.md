# Local development

From a clean checkout, prepare the local development environment and run the
same non-integration verification gate used by CI:

```bash
uv sync --frozen
npm ci
cp .env.example .env
cp packages/web/.env.local.example packages/web/.env.local
make verify
```

Populate the copied environment files only with values appropriate to your
development environment. Never commit real secrets or local environment files.
Normal unit tests use the dummy environment values configured in CI; integration,
network, golden, and performance tests remain opt-in.
