.PHONY: help install dev test lint format clean docker-up docker-down migrate db-reset

# =============================================================================
# HELP
# =============================================================================

help: ## Show this help message
	@echo "Phenomenological Evidence System - Make Commands"
	@echo "================================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# INSTALLATION & SETUP
# =============================================================================

install: ## Install production dependencies
	pip install -e .

dev: ## Install development dependencies
	pip install -e ".[dev]"
	pre-commit install

env: ## Create .env file from template
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file from template"; \
		echo "⚠ Please edit .env and add your configuration"; \
	else \
		echo "✗ .env file already exists"; \
	fi

setup: env dev ## Complete development setup
	@echo "✓ Development environment setup complete"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env and configure your settings"
	@echo "2. Run 'make docker-up' to start services"
	@echo "3. Run 'make migrate' to set up database"
	@echo "4. Run 'make run' to start the server"

# =============================================================================
# DEVELOPMENT
# =============================================================================

run: ## Run development server
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-prod: ## Run production server
	uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

shell: ## Open Python shell with app context
	python -i -c "from main import app; from database import get_db_session; from models import *; print('App context loaded. Use get_db_session() for database access.')"

# =============================================================================
# DATABASE
# =============================================================================

migrate: ## Run database migrations
	alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create MSG="description")
	@if [ -z "$(MSG)" ]; then \
		echo "Error: MSG required. Usage: make migrate-create MSG='description'"; \
		exit 1; \
	fi
	alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback one migration
	alembic downgrade -1

migrate-history: ## Show migration history
	alembic history --verbose

db-reset: ## Reset database (WARNING: destroys all data)
	@echo "⚠️  WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		python -c "from database import init_db, reset_database; init_db(); reset_database()"; \
		echo "✓ Database reset complete"; \
	else \
		echo "Cancelled"; \
	fi

db-shell: ## Open PostgreSQL shell
	docker-compose exec db psql -U conatus -d phenomenological_evidence

# =============================================================================
# DOCKER
# =============================================================================

docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services with Docker Compose
	docker-compose up -d
	@echo "✓ Services started"
	@echo "  - API: http://localhost:8000"
	@echo "  - Docs: http://localhost:8000/docs"
	@echo "  - Database: localhost:5432"

docker-up-tools: ## Start with pgAdmin
	docker-compose --profile tools up -d
	@echo "✓ Services started (including tools)"
	@echo "  - API: http://localhost:8000"
	@echo "  - Docs: http://localhost:8000/docs"
	@echo "  - pgAdmin: http://localhost:5050"

docker-down: ## Stop all services
	docker-compose down

docker-down-volumes: ## Stop services and remove volumes (WARNING: deletes data)
	docker-compose down -v

docker-logs: ## View Docker logs
	docker-compose logs -f

docker-logs-app: ## View application logs
	docker-compose logs -f app

docker-exec: ## Execute command in app container (usage: make docker-exec CMD="bash")
	docker-compose exec app $(CMD)

docker-restart: ## Restart all services
	docker-compose restart

# =============================================================================
# TESTING
# =============================================================================

test: ## Run all tests
	pytest

test-verbose: ## Run tests with verbose output
	pytest -v

test-coverage: ## Run tests with coverage report
	pytest --cov --cov-report=html --cov-report=term

test-unit: ## Run unit tests only
	pytest -m unit

test-integration: ## Run integration tests only
	pytest -m integration

test-watch: ## Run tests in watch mode
	pytest-watch

# =============================================================================
# CODE QUALITY
# =============================================================================

lint: ## Run all linters
	ruff check .
	mypy .

lint-fix: ## Fix linting issues
	ruff check --fix .

format: ## Format code with black
	black .
	ruff check --fix .

format-check: ## Check if code is formatted
	black --check .

type-check: ## Run type checking
	mypy .

pre-commit: ## Run pre-commit hooks on all files
	pre-commit run --all-files

# =============================================================================
# SECURITY
# =============================================================================

generate-keys: ## Generate cryptographic keys for .env
	@echo "Generating keys..."
	@echo ""
	@echo "MASTER_ENCRYPTION_KEY (Fernet):"
	@python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
	@echo ""
	@echo "SECRET_KEY (Session):"
	@python -c "import secrets; print(secrets.token_urlsafe(32))"
	@echo ""
	@echo "⚠️  Add these to your .env file and keep them secure!"

audit: ## Run security audit
	pip-audit

# =============================================================================
# DOCUMENTATION
# =============================================================================

docs-serve: ## Serve documentation locally
	mkdocs serve

docs-build: ## Build documentation
	mkdocs build

docs-deploy: ## Deploy documentation to GitHub Pages
	mkdocs gh-deploy

# =============================================================================
# CLEANUP
# =============================================================================

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	@echo "✓ Cleaned up generated files"

clean-all: clean docker-down-volumes ## Deep clean (including Docker volumes)
	@echo "✓ Deep clean complete"

# =============================================================================
# UTILITIES
# =============================================================================

check-env: ## Check if .env exists and has required variables
	@if [ ! -f .env ]; then \
		echo "✗ .env file not found. Run 'make env' to create it."; \
		exit 1; \
	fi
	@echo "✓ .env file exists"

health-check: ## Check if services are healthy
	@curl -f http://localhost:8000/health || (echo "✗ API not responding"; exit 1)
	@echo "✓ API is healthy"

version: ## Show version information
	@echo "Phenomenological Evidence System"
	@python -c "from config import get_settings; s = get_settings(); print(f'Version: {s.app_version}')"
	@python --version

# =============================================================================
# CI/CD
# =============================================================================

ci-test: install ## Run CI test suite
	pytest --cov --cov-report=xml
	ruff check .
	mypy .
	black --check .

ci-build: ## Build for CI/CD
	docker build -t phenomenological-evidence:latest .

# =============================================================================
# DEFAULT
# =============================================================================

.DEFAULT_GOAL := help
