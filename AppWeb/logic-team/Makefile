.PHONY: setup build up down logs migrate makemigrations superuser test lint format shell psql reset-db

setup:
	@test -f .env || cp .env.example .env
	@echo ".env listo"

build:
	docker compose build

up: setup
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

superuser:
	docker compose exec web python manage.py createsuperuser

test:
	docker compose exec web pytest

lint:
	docker compose exec web ruff check .

format:
	docker compose exec web ruff format .

shell:
	docker compose exec web python manage.py shell

psql:
	docker compose exec db sh -c 'psql -U $$POSTGRES_USER -d $$POSTGRES_DB'

reset-db:
	docker compose down -v
