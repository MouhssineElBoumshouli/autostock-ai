# The app for a shop's computer (docker-compose.prod.yml): one container, one port.
# 1. Build the website.
FROM node:22-alpine AS website
WORKDIR /website
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2. The server, which also serves the built website. No developer tools, no reload.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    WEBSITE_DIR=/app/website
WORKDIR /app
COPY backend/scripts/install-postgres-tools.sh /tmp/
RUN sh /tmp/install-postgres-tools.sh
COPY backend/requirements.txt .
RUN grep -v "^pytest" requirements.txt > requirements-shop.txt && pip install --no-cache-dir -r requirements-shop.txt
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/scripts ./scripts
COPY backend/app ./app
COPY --from=website /website/dist ./website
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=2)"
CMD ["python", "-m", "app.start"]
