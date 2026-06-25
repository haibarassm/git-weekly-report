FROM python:3.11-slim

WORKDIR /app

# 安装Git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖（可选 PIP_INDEX_URL 指定镜像源，默认 pypi.org）
ARG PIP_INDEX_URL=
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} -r requirements.txt

# 复制项目文件
COPY . .

# 创建输出目录和项目目录
RUN mkdir -p /app/output /app/project

# 赋予入口脚本执行权限
RUN chmod +x /app/docker-entrypoint.sh

# 设置环境变量
ENV PROJECT_BASE_DIR=/app/project
ENV PYTHONPATH=/app

# 暴露Gradio端口（容器内部7860）
EXPOSE 7860

# 入口：先测试，再启动
ENTRYPOINT ["/app/docker-entrypoint.sh"]
