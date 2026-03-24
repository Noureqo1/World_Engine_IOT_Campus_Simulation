@echo off
REM World Engine - Demo Script for Windows
REM Shows a quick demo of all features

echo ========================================
echo World Engine - Interactive Demo
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

echo [Step 1/5] Starting World Engine...
docker-compose down >nul 2>&1
docker-compose up -d

echo [Step 2/5] Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo [Step 3/5] Checking container status...
docker-compose ps

echo.
echo [Step 4/5] Sample MQTT telemetry (5 messages):
echo ========================================
docker exec world_engine_mqtt mosquitto_sub -t "campus/#" -C 5

echo.
echo [Step 5/5] Fleet health status:
echo ========================================
timeout /t 3 /nobreak >nul
docker exec world_engine_mqtt mosquitto_sub -t "campus/fleet/health" -C 1

echo.
echo ========================================
echo Demo Complete!
echo ========================================
echo.
echo What's running:
echo   - 200 IoT rooms publishing telemetry
echo   - MQTT broker on port 1883
echo   - SQLite database persisting state
echo   - Fault injection (check for "faults" field)
echo   - Night cycle (outside temp changing)
echo.
echo Next steps:
echo   View all logs:     docker-compose logs -f
echo   Subscribe to MQTT: docker exec world_engine_mqtt mosquitto_sub -t "campus/#" -v
echo   Stop demo:         docker-compose down
echo.
pause
