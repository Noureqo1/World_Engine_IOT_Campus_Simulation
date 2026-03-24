#!/bin/bash
# World Engine - Quick Start Script for Linux/Mac

set -e

echo "========================================"
echo "World Engine - Quick Start"
echo "========================================"
echo ""

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "[ERROR] Docker is not running!"
    echo "Please start Docker and try again."
    exit 1
fi

echo "[1/3] Stopping any existing containers..."
docker-compose down >/dev/null 2>&1 || true

echo "[2/3] Starting World Engine..."
docker-compose up -d

echo "[3/3] Waiting for services to be ready..."
sleep 5

echo ""
echo "========================================"
echo "World Engine Started Successfully!"
echo "========================================"
echo ""
echo "Available commands:"
echo "  View logs:     docker-compose logs -f"
echo "  Stop:          docker-compose down"
echo "  Status:        docker-compose ps"
echo ""
echo "MQTT Topics:"
echo "  All telemetry: docker exec world_engine_mqtt mosquitto_sub -t 'campus/#' -v"
echo "  Fleet health:  docker exec world_engine_mqtt mosquitto_sub -t 'campus/fleet/health' -v"
echo ""
