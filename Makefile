.PHONY: up down logs status clean help seed-demo seed-demo-reset

# Default target
help:
	@echo "Available targets:"
	@echo "  make up              - Start all services (postgres + kafka + kafka-ui + api + ui + all workers)"
	@echo "  make down            - Stop all services and workers"
	@echo "  make logs            - Tail worker logs"
	@echo "  make status          - Show status of all services"
	@echo "  make clean           - Stop all and remove volumes"
	@echo "  make seed-demo       - Seed demo data (idempotent)"
	@echo "  make seed-demo-reset - Reset and reseed all demo data"

# Start all services
up:
	@echo "=========================================="
	@echo "Starting Exception Platform Services"
	@echo "=========================================="
	@echo ""
	@echo "Starting Docker Compose services..."
	docker-compose up -d
	@echo ""
	@echo "Waiting for services to be healthy..."
	@echo "This may take 30-60 seconds..."
	@sleep 5
	@echo ""
	@echo "Starting workers..."
	@if [ -f "scripts/start-workers.sh" ]; then \
		bash scripts/start-workers.sh; \
	else \
		echo "Error: scripts/start-workers.sh not found"; \
		exit 1; \
	fi
	@echo ""
	@echo "=========================================="
	@echo "All services started!"
	@echo "=========================================="
	@echo ""
	@echo "Access points:"
	@echo "  UI:        http://localhost:3000"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo "  Kafka UI:  http://localhost:8080"
	@echo ""
	@echo "To view logs: make logs"
	@echo "To stop all:   make down"

# Stop all services
down:
	@echo "=========================================="
	@echo "Stopping Exception Platform Services"
	@echo "=========================================="
	@echo ""
	@echo "Stopping workers..."
	@if [ -f "scripts/stop-workers.sh" ]; then \
		bash scripts/stop-workers.sh; \
	else \
		echo "Warning: scripts/stop-workers.sh not found, skipping worker shutdown"; \
	fi
	@echo ""
	@echo "Stopping Docker Compose services..."
	docker-compose down
	@echo ""
	@echo "All services stopped."

# Tail worker logs
logs:
	@echo "Tailing worker logs (Ctrl+C to exit)..."
	@if [ -d "logs" ]; then \
		tail -f logs/worker-*.log 2>/dev/null || echo "No worker log files found in logs/"; \
	else \
		echo "Logs directory not found. Workers may not be running."; \
	fi

# Show status
status:
	@echo "=========================================="
	@echo "Service Status"
	@echo "=========================================="
	@echo ""
	@echo "Docker Compose services:"
	@docker-compose ps
	@echo ""
	@echo "Worker processes:"
	@if [ -d "logs" ]; then \
		for pidfile in logs/worker-*.pid; do \
			if [ -f "$$pidfile" ]; then \
				pid=$$(cat $$pidfile 2>/dev/null); \
				worker=$$(basename $$pidfile .pid | sed 's/worker-//'); \
				if ps -p $$pid > /dev/null 2>&1; then \
					echo "  $$worker: running (PID $$pid)"; \
				else \
					echo "  $$worker: not running"; \
				fi; \
			fi; \
		done; \
	else \
		echo "  No worker PID files found"; \
	fi

# Clean up everything (including volumes)
clean:
	@echo "=========================================="
	@echo "Cleaning Up All Services and Data"
	@echo "=========================================="
	@echo ""
	@echo "Stopping workers..."
	@if [ -f "scripts/stop-workers.sh" ]; then \
		bash scripts/stop-workers.sh; \
	fi
	@echo ""
	@echo "Stopping Docker Compose and removing volumes..."
	docker-compose down -v
	@echo ""
	@echo "Cleanup complete. All data has been removed."


# Seed demo data (idempotent - safe to run multiple times)
seed-demo:
	@echo "=========================================="
	@echo "Seeding Demo Data"
	@echo "=========================================="
	@echo ""
	python scripts/seed_demo.py
	@echo ""
	@echo "Demo data seeding complete!"

# Reset and reseed all demo data
seed-demo-reset:
	@echo "=========================================="
	@echo "Resetting and Reseeding Demo Data"
	@echo "=========================================="
	@echo ""
	python scripts/seed_demo.py --reset
	@echo ""
	@echo "Demo data reset complete!"
