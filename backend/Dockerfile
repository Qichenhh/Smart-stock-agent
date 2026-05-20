FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码
COPY . .

# 创建 .env（运行时通过 volume 挂载覆盖）
RUN cp -n .env.example .env 2>/dev/null || true

EXPOSE 8000

CMD ["python", "run.py"]
