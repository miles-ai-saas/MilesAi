# 注意：构建上下文必须为项目根目录（MilesAi/），确保 backend/ 在上下文中。
# 命令示例：docker buildx build --platform linux/amd64 -t <镜像> -f docker/images/api/Dockerfile .
FROM registry.cn-shenzhen.aliyuncs.com/kye_secure/python:3.11.9

WORKDIR /app

# 复制整个项目（上下文中需包含 backend/、ui/ 等）
COPY . .

# 安装 backend 包
RUN pip install --no-cache-dir -e backend -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com

ENV PYTHONPATH=/app/backend
WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
