# 注意：构建上下文必须为项目根目录（MilesAi/），确保 backend/ 在上下文中。
FROM registry.cn-shenzhen.aliyuncs.com/kye_secure/python:3.11.9

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir -e backend -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

CMD ["celery", "-A", "app.workers.app", "worker", "-l", "info", "-Q", "default,parse,ocr,asr,embed"]
