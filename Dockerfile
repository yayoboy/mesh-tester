# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build deps
RUN pip install --upgrade pip

COPY requirements.txt pyproject.toml ./
# Install runtime deps only (no dev extras)
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    paho-mqtt \
    rich \
    textual \
    PyYAML \
    meshtastic


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy source
COPY src/     src/
COPY web_main.py main.py ./

# Non-root user for security
RUN useradd -m mesh && chown -R mesh:mesh /app
USER mesh

# Default env (overridable at runtime / via docker-compose)
ENV WEB_HOST=0.0.0.0 \
    WEB_PORT=8080 \
    MQTT_BROKER=mosquitto \
    MQTT_PORT=1883 \
    MESH_ZONE=Milano \
    MESH_COUNT=5 \
    MESH_PREFIX=TST

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/status')" || exit 1

ENTRYPOINT ["python", "web_main.py"]
