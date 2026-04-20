# World Engine - IoT Campus Simulation
# Multi-stage build for optimized image size

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Ensure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY config.yaml .
COPY config.phase2.yaml .
COPY main.py .
COPY world_engine/ ./world_engine/

# Create directory for SQLite database
RUN mkdir -p /app/data

# Environment variables (can be overridden at runtime)
ENV MQTT_HOST=mosquitto
ENV MQTT_PORT=1883
ENV DB_PATH=/app/data/world_engine.db

# Expose metrics port (optional future use)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; asyncio.run(__import__('aiosqlite').connect('/app/data/world_engine.db'))" || exit 1

# Run the simulation
CMD ["python", "main.py"]
