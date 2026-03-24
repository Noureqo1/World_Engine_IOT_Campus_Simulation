@echo off
REM World Engine - Stop Script for Windows

echo ========================================
echo Stopping World Engine...
echo ========================================
echo.

docker-compose down

echo.
echo ========================================
echo World Engine Stopped Successfully!
echo ========================================
echo.
echo To remove all data (database, logs):
echo   docker-compose down -v
echo.
pause
