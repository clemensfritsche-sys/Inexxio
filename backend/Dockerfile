# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps needed to compile some Python packages (psycopg2, cryptography)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime image ─────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime-only system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN useradd --system --uid 1001 --no-create-home appuser

# Copy application source
COPY . .

# Startup script: run Alembic migrations, then start uvicorn
RUN cat > /app/start.sh << 'EOF'
#!/bin/bash
set -e

echo "[startup] Running Alembic migrations..."
alembic upgrade head

echo "[startup] Starting uvicorn on port 8080..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers 2 \
  --loop uvloop \
  --http httptools \
  --log-level info \
  --no-access-log
EOF

RUN chmod +x /app/start.sh

# Cloud Run listens on 8080
EXPOSE 8080

# Switch to non-root user
USER appuser

# Health check (Cloud Run also provides its own)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/health')" || exit 1

CMD ["/app/start.sh"]
