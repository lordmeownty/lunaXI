# Build context: repository root  (docker build -f backend/Dockerfile .)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LUNA_DATA_DIR=/app/data LUNA_STATE_DIR=/tmp/luna-state
WORKDIR /app
COPY backend/requirements.txt backend/requirements-agents.txt /app/backend/
RUN pip install --no-cache-dir -r /app/backend/requirements.txt && (pip install --no-cache-dir --pre -r /app/backend/requirements-agents.txt || echo "Agent Framework not installed; builtin engine will be used")
COPY backend /app/backend
COPY data /app/data
COPY services /app/services
WORKDIR /app/backend
RUN useradd -m luna && chown -R luna /app
USER luna
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
