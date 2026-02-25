FROM python:3.14-slim-bookworm AS builder

# Install uv
RUN pip install "uv>=0.9.28"

# Copy requirements and install dependencies
WORKDIR /opt/app
COPY requirements.txt .
RUN uv venv /opt/venv
RUN uv pip install --python /opt/venv/bin/python -r requirements.txt

# Final stage
FROM python:3.14-slim-bookworm

# Copy virtual environment from builder
COPY --from=builder /opt/venv /home/appuser/.venv
RUN sed -i 's|#!/opt/venv/bin/python|#!/home/appuser/.venv/bin/python|g' /home/appuser/.venv/bin/gunicorn /home/appuser/.venv/bin/gunicorn_paster /home/appuser/.venv/bin/futurize /home/appuser/.venv/bin/pasteaster 2>/dev/null || true
COPY --chmod=755 url_check.py run.sh scheduler_runner.py gunicorn.conf.py test_alerts.py /home/appuser/
COPY conf/ /home/appuser/conf/
COPY view/ /home/appuser/view/

# Create non-root user and set permissions
RUN adduser --disabled-password --gecos "" --shell /bin/bash --home /home/appuser appuser && \
    chown -R appuser:appuser /home/appuser
USER appuser:appuser
WORKDIR /home/appuser

# Expose port
EXPOSE 4000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:4000/health', timeout=2)"

# Entrypoint wrapper (safe, debuggable)
ENTRYPOINT ["/home/appuser/run.sh"]
