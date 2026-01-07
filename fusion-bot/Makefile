# ══════════════════════════════════════════════════════════════════════════════
# FusionBot Makefile
# ══════════════════════════════════════════════════════════════════════════════
# Convenient commands for Docker operations
#
# Usage:
#   make help          - Show all commands
#   make dry-run       - Start paper trading
#   make prod          - Start live trading (REAL MONEY!)
#   make logs-dry      - View dry run logs
#   make logs-prod     - View production logs
#   make stop          - Stop all containers
# ══════════════════════════════════════════════════════════════════════════════

.PHONY: help build dry-run prod stop logs-dry logs-prod status clean db-shell

# Default target
help:
	@echo "══════════════════════════════════════════════════════════════════"
	@echo "  FusionBot Commands"
	@echo "══════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup-dry     Copy template to .env.dry_run"
	@echo "    make setup-testnet Copy template to .env.testnet"
	@echo "    make setup-prod    Copy template to .env.prod"
	@echo "    make build         Build Docker images"
	@echo ""
	@echo "  Run (progression: dry-run → testnet → prod):"
	@echo "    make dry-run       Paper trading (100% simulated)"
	@echo "    make testnet       Binance Testnet (real API, fake money)"
	@echo "    make prod          Live trading (REAL MONEY!)"
	@echo ""
	@echo "  Monitor:"
	@echo "    make logs-dry      Follow dry run logs"
	@echo "    make logs-testnet  Follow testnet logs"
	@echo "    make logs-prod     Follow production logs"
	@echo "    make status        Show container status"
	@echo ""
	@echo "  Control:"
	@echo "    make stop          Stop all containers"
	@echo "    make restart-dry   Restart dry run"
	@echo "    make restart-testnet Restart testnet"
	@echo "    make restart-prod  Restart production"
	@echo ""
	@echo "  Database:"
	@echo "    make db-shell      Open PostgreSQL shell"
	@echo "    make db-ui         Start Adminer (DB UI on :8080)"
	@echo ""
	@echo "  Cleanup:"
	@echo "    make clean         Stop and remove containers"
	@echo "    make clean-all     Remove everything including volumes"
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════"

# ══════════════════════════════════════════════════════════════════════════════
# Setup
# ══════════════════════════════════════════════════════════════════════════════

setup-dry:
	@if [ ! -f .env.dry_run ]; then \
		cp env.dry_run.template .env.dry_run; \
		echo "✅ Created .env.dry_run - please edit with your API keys"; \
	else \
		echo "⚠️  .env.dry_run already exists"; \
	fi

setup-testnet:
	@if [ ! -f .env.testnet ]; then \
		cp env.testnet.template .env.testnet; \
		echo "✅ Created .env.testnet - please edit with your TESTNET API keys"; \
		echo "📝 Get testnet keys from: https://testnet.binance.vision/"; \
	else \
		echo "⚠️  .env.testnet already exists"; \
	fi

setup-prod:
	@if [ ! -f .env.prod ]; then \
		cp env.prod.template .env.prod; \
		echo "✅ Created .env.prod - please edit with your API keys"; \
		echo "⚠️  WARNING: This is for REAL MONEY trading!"; \
	else \
		echo "⚠️  .env.prod already exists"; \
	fi

build:
	@echo "🔨 Building FusionBot Docker image..."
	docker compose build

# ══════════════════════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════════════════════

dry-run: setup-dry
	@echo "🧪 Starting FusionBot in DRY RUN mode (paper trading)..."
	docker compose --profile dry_run up -d --force-recreate
	@echo ""
	@echo "✅ Dry run started! View logs with: make logs-dry"

testnet: setup-testnet
	@echo "🔗 Starting FusionBot in TESTNET mode (real API, fake money)..."
	docker compose --profile testnet up -d
	@echo ""
	@echo "✅ Testnet started! View logs with: make logs-testnet"

prod: setup-prod
	@echo "⚠️  WARNING: Starting FusionBot in PRODUCTION mode!"
	@echo "⚠️  This uses REAL MONEY. Are you sure?"
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	docker compose --profile prod up -d
	@echo ""
	@echo "✅ Production started! View logs with: make logs-prod"

all-envs: setup-dry setup-testnet setup-prod
	@echo "🔄 Starting BOTH environments..."
	docker compose --profile dry_run --profile prod up -d

# ══════════════════════════════════════════════════════════════════════════════
# Monitor
# ══════════════════════════════════════════════════════════════════════════════

logs-dry:
	docker compose logs -f fusionbot-dry-run

logs-testnet:
	docker compose logs -f fusionbot-testnet

logs-prod:
	docker compose logs -f fusionbot-prod

logs-db:
	docker compose logs -f postgres

status:
	@echo "══════════════════════════════════════════════════════════════════"
	@echo "  FusionBot Status"
	@echo "══════════════════════════════════════════════════════════════════"
	@docker compose ps
	@echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Control
# ══════════════════════════════════════════════════════════════════════════════

stop:
	@echo "🛑 Stopping all FusionBot containers..."
	docker compose --profile dry_run --profile testnet --profile prod --profile tools down

restart-dry:
	docker compose --profile dry_run restart fusionbot-dry-run

restart-testnet:
	docker compose --profile testnet restart fusionbot-testnet

restart-prod:
	docker compose --profile prod restart fusionbot-prod

# ══════════════════════════════════════════════════════════════════════════════
# Database
# ══════════════════════════════════════════════════════════════════════════════

db-shell:
	docker compose exec postgres psql -U fusionbot -d fusionbot

db-ui:
	@echo "🌐 Starting Adminer on http://localhost:8080"
	docker compose --profile tools up -d adminer
	@echo "Connect with:"
	@echo "  System: PostgreSQL"
	@echo "  Server: postgres"
	@echo "  User: fusionbot"
	@echo "  Database: fusionbot_dry_run or fusionbot_prod"

# ══════════════════════════════════════════════════════════════════════════════
# Cleanup
# ══════════════════════════════════════════════════════════════════════════════

clean:
	@echo "🧹 Stopping and removing containers..."
	docker compose --profile dry_run --profile testnet --profile prod --profile tools down

clean-all:
	@echo "⚠️  This will remove ALL data including database!"
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	docker compose --profile dry_run --profile testnet --profile prod --profile tools down -v
	rm -rf data/ logs/
	@echo "✅ All cleaned up"

# ══════════════════════════════════════════════════════════════════════════════
# Development
# ══════════════════════════════════════════════════════════════════════════════

shell-dry:
	docker compose exec fusionbot-dry-run /bin/bash

shell-prod:
	docker compose exec fusionbot-prod /bin/bash

