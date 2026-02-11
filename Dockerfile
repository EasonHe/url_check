# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm AS builder

# Install uv
RUN pip install "uv>=0.9.28"

# Copy requirements and install dependencies into /opt/venv
WORKDIR /opt/app
COPY requirements.txt .
RUN uv venv /opt/venv && \
    uv pip install --python-version 3.14 --system-site-packages -r requirements.txt

# Final stage
FROM python:3.14-slim-bookworm

# Create non-root user
RUN adduser --disabled-password --gecos "" --shell /bin/bash --home /home/appuser appuser && \
    chown -R appuser:appuser /home/appuser
USER appuser:appuser
WORKDIR /home/appuser

# Copy only runtime files from builder
COPY --from=builder /opt/venv /home/appuser/.venv
COPY url_check.py run.sh ./
RUN chmod +x run.sh

# Expose port
EXPOSE 4000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:4000/health || exit 1

# Entrypoint wrapper (safe, debuggable)
ENTRYPOINT ["/home/appuser/run.sh"]