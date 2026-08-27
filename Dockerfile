FROM node:22-alpine AS frontend-build
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
COPY packages/api-client /packages/api-client
RUN pnpm build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIXELVAULT_ENV=production \
    PIXELVAULT_STATIC_DIR=/app/frontend \
    DATA_DIR=/app/data \
    PORT=8000
WORKDIR /app
RUN useradd --create-home --uid 10001 pixelvault
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./frontend
RUN mkdir -p /app/data && chown -R pixelvault:pixelvault /app
USER pixelvault
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-m", "app.healthcheck"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\" --proxy-headers --forwarded-allow-ips='*'"]
