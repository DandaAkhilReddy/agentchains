# Stage 1: Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim

LABEL maintainer="AgentChains Team"
LABEL description="Agent-to-Agent Data Marketplace — v1.0"

WORKDIR /app

# Create non-root user
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

# Install system dependencies for grpcio and azure SDKs
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY marketplace/ marketplace/
COPY agents/ agents/
COPY --from=frontend-build /frontend/dist/ static/

RUN mkdir -p data/content_store && chown -R appuser:appgroup data/

ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/v1/health')" || exit 1

USER appuser

CMD ["uvicorn", "marketplace.main:app", "--host", "0.0.0.0", "--port", "8080"]
