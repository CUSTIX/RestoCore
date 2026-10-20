.PHONY: install lock run shell makemigrations migrate test lint format check migrations-check pre-commit

install:
	uv sync --all-groups

lock:
	uv lock

run:
	uv run python manage.py runserver

shell:
	uv run python manage.py shell

makemigrations:
	uv run python manage.py makemigrations

migrate:
	uv run python manage.py migrate

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

migrations-check:
	uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test

check: lint migrations-check
	uv run ruff format --check .
	uv run python manage.py check --settings=config.settings.test
	uv run pytest

pre-commit:
	uv run pre-commit install
