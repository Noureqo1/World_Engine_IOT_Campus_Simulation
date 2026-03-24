.PHONY: help setup install run run-mock docker-up docker-down docker-logs \
        test-mqtt test-db clean restart subscribe health metrics db-status

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

#==============================================================================
# Help
#==============================================================================

help: ## Show this help message
	@echo "$(BLUE)World Engine - IoT Campus Simulation$(NC)"
	@echo "$(YELLOW)Available commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

#==============================================================================
# Environment Setup
#==============================================================================

setup: ## Create virtual environment and install dependencies
	@echo "$(BLUE)Creating virtual environment...$(NC)"
	python -m venv venv
	@echo "$(GREEN)Virtual environment created!$(NC)"
	@echo "$(YELLOW)Activate with: source venv/Scripts/activate$(NC)"

install: ## Install Python dependencies
	@echo "$(BLUE)Installing dependencies...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)Dependencies installed!$(NC)"

init-db: ## Initialize SQLite database
	@echo "$(BLUE)Initializing database...$(NC)"
	python -c "from world_engine.db.db_setup import init_database; import asyncio; asyncio.run(init_database())"
	@echo "$(GREEN)Database initialized!$(NC)"

#==============================================================================
# Running the Simulation
#==============================================================================

run: ## Run simulation with MQTT broker (requires Mosquitto)
	@echo "$(BLUE)Starting World Engine simulation...$(NC)"
	python main.py

run-mock: ## Run simulation in mock mode (no MQTT broker needed)
	@echo "$(BLUE)Starting World Engine in MOCK mode...$(NC)"
	python main.py --mock

#==============================================================================
# Docker Commands
#==============================================================================

docker-up: ## Start containers (Mosquitto + World Engine)
	@echo "$(BLUE)Starting Docker containers...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Containers started!$(NC)"
	@echo "$(YELLOW)View logs: make docker-logs$(NC)"

docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker-compose build

docker-down: ## Stop and remove containers
	@echo "$(BLUE)Stopping containers...$(NC)"
	docker-compose down
	@echo "$(GREEN)Containers stopped!$(NC)"

docker-logs: ## Show container logs (follow mode)
	docker-compose logs -f

docker-restart: ## Restart containers
	@echo "$(BLUE)Restarting containers...$(NC)"
	docker-compose restart
	@echo "$(GREEN)Containers restarted!$(NC)"

docker-ps: ## Show container status
	docker-compose ps

#==============================================================================
# MQTT Testing
#==============================================================================

subscribe: ## Subscribe to all campus MQTT topics
	@echo "$(BLUE)Subscribing to campus/# topics...$(NC)"
	docker exec world_engine_mqtt mosquitto_sub -t "campus/#" -v

subscribe-room: ## Subscribe to a specific room (usage: make subscribe-room ROOM=101)
	@echo "$(BLUE)Subscribing to room $(ROOM) telemetry...$(NC)"
	docker exec world_engine_mqtt mosquitto_sub -t "campus/b01/floor_01/room_$(ROOM)/telemetry" -v

health: ## Subscribe to fleet health messages
	@echo "$(BLUE)Monitoring fleet health...$(NC)"
	docker exec world_engine_mqtt mosquitto_sub -t "campus/fleet/health" -v

metrics: ## Subscribe to performance metrics
	@echo "$(BLUE)Monitoring performance metrics...$(NC)"
	docker exec world_engine_mqtt mosquitto_sub -t "campus/fleet/metrics" -v

mosquitto-status: ## Check Mosquitto broker status
	docker exec world_engine_mqtt mosquitto_sub -t '$$SYS/#' -C 10

#==============================================================================
# Database Operations
#==============================================================================

db-status: ## Show database statistics
	@echo "$(BLUE)Database Statistics:$(NC)"
	@docker exec world_engine_sim python -c "\
	import sqlite3; \
	conn = sqlite3.connect('/app/data/world_engine.db'); \
	cursor = conn.cursor(); \
	cursor.execute('SELECT COUNT(*) FROM room_states'); \
	print('Total rooms:', cursor.fetchone()[0]); \
	cursor.execute('SELECT AVG(last_temp), AVG(last_humidity) FROM room_states'); \
	avg = cursor.fetchone(); \
	print(f'Avg temperature: {avg[0]:.1f}°C'); \
	print(f'Avg humidity: {avg[1]:.1f}%'); \
	conn.close()"

db-query: ## Run custom SQL query (usage: make db-query SQL="SELECT * FROM room_states LIMIT 5")
	docker exec world_engine_sim python -c "\
	import sqlite3; \
	conn = sqlite3.connect('/app/data/world_engine.db'); \
	cursor = conn.cursor(); \
	cursor.execute('$(SQL)'); \
	for row in cursor.fetchall(): print(row); \
	conn.close()"

db-backup: ## Backup database to local file
	@echo "$(BLUE)Backing up database...$(NC)"
	docker cp world_engine_sim:/app/data/world_engine.db ./world_engine_backup.db
	@echo "$(GREEN)Database backed up to world_engine_backup.db$(NC)"

db-reset: ## Clear all room states from database
	@echo "$(YELLOW)Warning: This will delete all room states!$(NC)"
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ]
	docker exec world_engine_sim python -c "\
	import sqlite3; \
	conn = sqlite3.connect('/app/data/world_engine.db'); \
	conn.execute('DELETE FROM room_states'); \
	conn.commit(); \
	print('Database cleared'); \
	conn.close()"

#==============================================================================
# Testing & Validation
#==============================================================================

test-mqtt: ## Test MQTT connection
	@echo "$(BLUE)Testing MQTT connection...$(NC)"
	docker exec world_engine_mqtt mosquitto_pub -t "test" -m "Hello from World Engine"
	@echo "$(GREEN)MQTT test message published!$(NC)"

test-sensors: ## Show sample sensor readings
	@echo "$(BLUE)Sample sensor readings:$(NC)"
	docker exec world_engine_mqtt mosquitto_sub -t "campus/b01/floor_01/room_101/telemetry" -C 1

validate: ## Validate project structure
	@echo "$(BLUE)Validating project structure...$(NC)"
	@test -f config.yaml && echo "$(GREEN)✓$(NC) config.yaml" || echo "$(YELLOW)✗$(NC) config.yaml missing"
	@test -f requirements.txt && echo "$(GREEN)✓$(NC) requirements.txt" || echo "$(YELLOW)✗$(NC) requirements.txt missing"
	@test -f main.py && echo "$(GREEN)✓$(NC) main.py" || echo "$(YELLOW)✗$(NC) main.py missing"
	@test -f Dockerfile && echo "$(GREEN)✓$(NC) Dockerfile" || echo "$(YELLOW)✗$(NC) Dockerfile missing"
	@test -f docker-compose.yaml && echo "$(GREEN)✓$(NC) docker-compose.yaml" || echo "$(YELLOW)✗$(NC) docker-compose.yaml missing"
	@test -d world_engine && echo "$(GREEN)✓$(NC) world_engine/" || echo "$(YELLOW)✗$(NC) world_engine/ missing"

lint: ## Run code linting (if pylint installed)
	@echo "$(BLUE)Running linter...$(NC)"
	@pylint world_engine/ main.py || echo "$(YELLOW)Install pylint: pip install pylint$(NC)"

#==============================================================================
# Development
#==============================================================================

shell: ## Open shell in simulation container
	docker exec -it world_engine_sim /bin/bash

mqtt-shell: ## Open shell in MQTT container
	docker exec -it world_engine_mqtt /bin/sh

clean: ## Clean up generated files and caches
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -f world_engine.db 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"

clean-all: clean docker-down ## Deep clean (includes Docker volumes)
	@echo "$(BLUE)Removing Docker volumes...$(NC)"
	docker volume rm iot_mosquitto_data iot_mosquitto_log iot_world_engine_data 2>/dev/null || true
	@echo "$(GREEN)Deep clean complete!$(NC)"

#==============================================================================
# Quick Start
#==============================================================================

quickstart: setup install init-db ## Complete first-time setup
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  1. Activate venv: $(BLUE)source venv/Scripts/activate$(NC)"
	@echo "  2. Run simulation: $(BLUE)make run-mock$(NC)"
	@echo "  3. Or use Docker: $(BLUE)make docker-up$(NC)"
	@echo "$(GREEN)========================================$(NC)"

demo: docker-up ## Start demo with live monitoring
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)World Engine Demo Started!$(NC)"
	@echo "$(GREEN)========================================$(NC)"
	@echo ""
	@echo "$(YELLOW)View live logs with: make docker-logs$(NC)"
	@echo "$(YELLOW)Or run: docker-compose logs -f$(NC)"
	@echo ""
	@echo "$(BLUE)To stop:$(NC) make docker-down"
	@echo ""
	@echo "$(BLUE)Subscribe to MQTT:$(NC) make subscribe"
	@echo "$(BLUE)View health:$(NC) make health"
	@echo "$(BLUE)View metrics:$(NC) make metrics"
