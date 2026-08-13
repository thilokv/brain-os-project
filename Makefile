.PHONY: build up down logs restart shell test test-local health clean

# Container lifecycle (requires Docker + the Docker Compose plugin)
build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f brain-os

restart:
	docker compose restart brain-os

shell:
	docker compose exec brain-os /bin/bash

health:
	curl -fsS http://localhost:8000/health

# Run the pytest suite inside a throwaway container built from the
# Dockerfile's `test` stage (production `runtime` image never ships tests/)
test:
	docker build --target test -t brain-os-enterprise-workflow-platform:test .
	docker run --rm brain-os-enterprise-workflow-platform:test

# Run the pytest suite against the local .venv (no Docker required)
test-local:
	.venv/bin/python -m pytest -v

clean:
	docker compose down -v --remove-orphans
