#!/bin/bash
# Bash script to manage PostgreSQL Docker container
# Usage:
#   ./scripts/docker_db.sh start    - Start PostgreSQL container
#   ./scripts/docker_db.sh stop     - Stop PostgreSQL container
#   ./scripts/docker_db.sh restart  - Restart PostgreSQL container
#   ./scripts/docker_db.sh status   - Check container status
#   ./scripts/docker_db.sh logs     - Show container logs
#   ./scripts/docker_db.sh shell    - Open psql shell in container
#   ./scripts/docker_db.sh remove   - Remove container and volumes

CONTAINER_NAME="sentinai-postgres"
COMMAND=${1:-status}

show_status() {
    echo ""
    echo "=== PostgreSQL Docker Container Status ==="
    docker ps -a --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
}

start_container() {
    echo "Starting PostgreSQL container..."
    docker-compose up -d postgres
    
    echo "Waiting for PostgreSQL to be ready..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        health=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER_NAME 2>/dev/null)
        if [ "$health" = "healthy" ]; then
            echo "[OK] PostgreSQL is ready!"
            echo ""
            echo "Connection details:"
            echo "  Host: localhost"
            echo "  Port: 5432"
            echo "  Database: sentinai"
            echo "  Username: postgres"
            echo "  Password: postgres"
            echo ""
            echo "DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"
            return
        fi
        sleep 1
        echo -n "."
        attempt=$((attempt + 1))
    done
    
    echo ""
    echo "[WARNING] Container started but health check timed out"
    echo "Check logs with: docker-compose logs postgres"
}

stop_container() {
    echo "Stopping PostgreSQL container..."
    docker-compose stop postgres
    echo "[OK] Container stopped"
}

restart_container() {
    echo "Restarting PostgreSQL container..."
    docker-compose restart postgres
    sleep 2
    show_status
}

show_logs() {
    echo "=== PostgreSQL Container Logs ==="
    docker-compose logs -f postgres
}

open_shell() {
    echo "Opening psql shell..."
    docker exec -it $CONTAINER_NAME psql -U postgres -d sentinai
}

remove_container() {
    echo "WARNING: This will remove the container and all data!"
    read -p "Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
        echo "Removing container and volumes..."
        docker-compose down -v
        echo "[OK] Container and volumes removed"
    else
        echo "Cancelled"
    fi
}

case $COMMAND in
    start)
        start_container
        ;;
    stop)
        stop_container
        ;;
    restart)
        restart_container
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    shell)
        open_shell
        ;;
    remove)
        remove_container
        ;;
    *)
        show_status
        ;;
esac

