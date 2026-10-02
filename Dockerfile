FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project specification & dependencies
COPY pyproject.toml .
COPY README.md .
COPY LICENSE .
RUN pip install --no-cache-dir ".[all]"

# Copy application source code
COPY aegis/ ./aegis/
COPY benchmarks/ ./benchmarks/

# Security: non-root user execution
RUN useradd -m -s /bin/bash aira && chown -R aira:aira /app
USER aira

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DEMO_MODE=false
ENV PYTHONUNBUFFERED=1

# Expose HTTP port
EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start A.I.R.A. Verification Service with Web UI
CMD ["uvicorn", "aegis.api.service:app", "--host", "0.0.0.0", "--port", "8000"]
