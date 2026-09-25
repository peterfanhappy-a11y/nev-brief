.PHONY: help install dev down test-unit test-web test-ops test-integration lint typecheck verify verify-vercel-target deploy-web-production format clean

help:
	@echo "make install   # 安装所有依赖 (uv + npm)"
	@echo "make dev       # 启动本地 docker-compose (Postgres + RSSHub)"
	@echo "make down      # 停止 docker-compose"
	@echo "make test-unit        # 跑默认 Python 单元测试"
	@echo "make test-web         # 跑 Web Vitest 单元测试"
	@echo "make test-ops         # 跑发布后首页刷新契约测试"
	@echo "make test-integration # 跑 Python 集成测试"
	@echo "make lint      # ruff + web eslint"
	@echo "make typecheck # scoped mypy + web TypeScript"
	@echo "make verify    # unit tests + lint + typecheck + web production build"
	@echo "make verify-vercel-target # confirm the local Vercel link is production"
	@echo "make deploy-web-production # guarded emergency Vercel production deploy"
	@echo "make format    # ruff format"
	@echo "make clean     # 清理缓存"

install:
	uv sync
	npm install

dev:
	cd infra && docker compose up -d
	@echo "Postgres: localhost:54322"
	@echo "RSSHub:   localhost:1200"

down:
	cd infra && docker compose down

test-unit:
	uv run pytest -c pyproject.toml packages tests -q

test-web:
	npm --workspace @nev/web run test

test-ops:
	bash ops/launchd/test-homepage-refresh.sh

test-integration:
	uv run pytest -c pyproject.toml packages tests -m integration -q

lint:
	uv run ruff check packages/
	npm --workspace @nev/web run lint

typecheck:
	uv run mypy packages/ai-brief packages/shared
	npm --workspace @nev/web run typecheck

verify: test-unit test-web test-ops lint typecheck
	npm --workspace @nev/web run build
	npm --workspace @nev/web run verify:brand-assets
	npm --workspace @nev/web run verify:homepage-isr

verify-vercel-target:
	uv run python scripts/ci/verify_vercel_project.py

deploy-web-production: verify-vercel-target
	npx vercel@latest --prod

format:
	uv run ruff format packages/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv node_modules
