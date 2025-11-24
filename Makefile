# Makefile for Garage Management System

.PHONY: help build up down restart logs clean test dev prod

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker images
	docker compose build

up: ## Start services in production mode
	docker compose up -d

dev: ## Start services in development mode
	docker compose -f docker-compose.dev.yml up

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## View logs (use `make logs service=api` for specific service)
	docker compose logs -f $(service)

clean: ## Remove containers, volumes, and images
	docker compose down -v --rmi all

test: ## Run tests
	docker compose exec api pytest

shell-api: ## Access API container shell
	docker compose exec api sh

shell-db: ## Access PostgreSQL shell
	docker compose exec db psql -U garage_user -d garage_db

migrate: ## Run database migrations (when Alembic is set up)
	docker compose exec api alembic upgrade head

env: ## Create .env file from example
	cp .env.example .env
	@echo "Don't forget to update SECRET_KEY in .env!"

secret: ## Generate a secure secret key
	@python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

init: env build up ## Initialize project (create .env, build, and start)
	@echo "✅ Project initialized!"
	@echo "🌐 API: http://localhost:8000"
	@echo "📖 Docs: http://localhost:8000/docs"

prod: ## Deploy in production mode
	docker compose up -d --build
	@echo "✅ Production deployment complete!"
	@echo "🌐 API: http://localhost:8000"
