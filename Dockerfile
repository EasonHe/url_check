# syntax=docker/dockerfile:1
FROM python:3.14-slim-bookworm AS builder

# Install uv
RUN pip install "uv>=0.9.28"

# Copy requirements and install dependencies into /opt/venv
WORKDIR /opt/app
COPY requirements.txt .
RUN uv venv /opt/venv
RUN uv pip install --system -r requirements.txt

# Final stage
FROM python:3.14-slim-bookworm

# Copy only runtime files from builder
COPY --from=builder /opt/venv /home/appuser/.venv
COPY --chmod=755 url_check.py run.sh ./
COPY conf/ ./conf/
COPY view/ ./view/

# Create non-root user and set permissions
RUN adduser --disabled-password --gecos "" --shell /bin/bash --home /home/appuser appuser && \
    chown -R appuser:appuser /home/appuser
USER appuser:appuser
WORKDIR /home/appuser

# Expose port
EXPOSE 4000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:4000/health || exit 1

# Entrypoint wrapper (safe, debuggable)
ENTRYPOINT ["/home/appuser/run.sh"]
