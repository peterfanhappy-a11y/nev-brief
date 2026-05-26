.PHONY: help install dev down test lint format clean

help:
	@echo "make install   # 安装所有依赖 (uv + npm)"
	@echo "make dev       # 启动本地 docker-compose (Postgres + RSSHub)"
	@echo "make down      # 停止 docker-compose"
	@echo "make test      # 跑所有 Python 测试"
	@echo "make lint      # ruff + mypy + eslint"
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

test:
	uv run pytest packages/ -v

test-integration:
	uv run pytest tests/integration/ -v -m integration

lint:
	uv run ruff check packages/
	uv run mypy packages/
	npm run lint --if-present

format:
	uv run ruff format packages/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv node_modules
