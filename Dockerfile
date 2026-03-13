FROM python:3.11-slim

WORKDIR /app

# 安装Git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建输出目录和项目目录
RUN mkdir -p /app/output /app/project

# 设置环境变量
ENV PROJECT_BASE_DIR=/app/project
ENV PYTHONPATH=/app/src:$PYTHONPATH

# 暴露Gradio端口
EXPOSE 7860

# 启动命令 - 使用启动脚本
CMD ["python", "/app/run_app.py"]
