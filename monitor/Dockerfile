# DSA moderation monitor (Task 5): Streamlit dashboard over the monthly totals.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

RUN pip install --no-cache-dir "uv>=0.11.19,<0.12"

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY codefinder ./codefinder
COPY service ./service
COPY monitor ./monitor
RUN uv sync --frozen --no-dev --package monitor

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home appuser
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]

CMD ["streamlit", "run", "monitor/src/monitor/dashboard.py", "--server.address=0.0.0.0", "--server.port=8501"]
