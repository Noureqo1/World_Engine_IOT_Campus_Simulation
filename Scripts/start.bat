@echo off
REM World Engine - Quick Start Script for Windows
REM This script helps you get started quickly

echo ========================================
echo World Engine - Quick Start
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [1/3] Stopping any existing containers...
docker-compose down >nul 2>&1

echo [2/3] Starting World Engine...
docker-compose up -d

echo [3/3] Waiting for services to be ready...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo World Engine Started Successfully!
echo ========================================
echo.
echo Available commands:
echo   View logs:     docker-compose logs -f
echo   Stop:          docker-compose down
echo   Status:       docker-compose ps
echo.
echo MQTT Topics:
echo   All telemetry: docker exec world_engine_mqtt mosquitto_sub -t "campus/#" -v
echo   Fleet health:  docker exec world_engine_mqtt mosquitto_sub -t "campus/fleet/health" -v
echo.
pause
