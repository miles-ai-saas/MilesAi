# 注意：构建上下文必须为项目根目录（MilesAi/），确保 backend/ 在上下文中。
FROM registry.cn-shenzhen.aliyuncs.com/kye_secure/python:3.11.9

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @modelcontextprotocol/server-everything@0.6.2 \
    && npm cache clean --force

COPY . .

RUN pip install --no-cache-dir -e backend -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

RUN useradd -m -u 10001 runner && chown -R runner:runner /app /tmp
USER runner

EXPOSE 8090

CMD ["uvicorn", "app.runner.main:app", "--host", "0.0.0.0", "--port", "8090"]
