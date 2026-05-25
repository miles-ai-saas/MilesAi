FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @modelcontextprotocol/server-everything@0.6.2 \
    && npm cache clean --force

COPY backend/pyproject.toml backend/README.md /app/backend/
RUN pip install --no-cache-dir -e /app/backend/

COPY backend /app/backend/

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

RUN useradd -m -u 10001 runner && chown -R runner:runner /app /tmp
USER runner

EXPOSE 8090

CMD ["uvicorn", "app.runner.main:app", "--host", "0.0.0.0", "--port", "8090"]
