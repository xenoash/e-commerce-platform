.PHONY: up down logs seed reset demo test lint schema web-check zatca-check

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker beat

seed:
	docker compose exec api python manage.py seed_demo

reset:
	docker compose exec api python manage.py seed_demo --reset

demo:
	cd backend && uv run python scripts/demo.py --base-url http://localhost:8100

test:
	cd backend && uv run pytest -n auto --cov --cov-report=term

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

schema:
	cd backend && uv run python manage.py spectacular --validate --fail-on-warn --file openapi.yaml
	cd web && npm run api:types

web-check:
	cd web && npm run typecheck && npm run lint && npm test && npm run build

zatca-check:
	docker compose exec api python manage.py zatca_compliance_check
