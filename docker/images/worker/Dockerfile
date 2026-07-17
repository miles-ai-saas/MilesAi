FROM registry.cn-shenzhen.aliyuncs.com/kye_secure/python:3.11.9

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/README.md /app/backend/
RUN pip install --no-cache-dir -e /app/backend/

COPY backend /app/backend/

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

CMD ["celery", "-A", "app.workers.app", "worker", "-l", "info", "-Q", "default,parse,ocr,asr,embed"]
