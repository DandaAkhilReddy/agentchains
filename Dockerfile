# Stage 1: Build React frontend
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY marketplace/ marketplace/
COPY agents/ agents/
COPY --from=frontend-build /frontend/dist/ static/

RUN mkdir -p data/content_store

ENV PORT=8080

CMD ["uvicorn", "marketplace.main:app", "--host", "0.0.0.0", "--port", "8080"]
