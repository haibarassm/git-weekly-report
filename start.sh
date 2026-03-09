#!/bin/bash

echo "==================================="
echo "  NAPS Git Weekly Report Generator"
echo "==================================="
echo ""

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker未运行，请先启动Docker"
    exit 1
fi

# 检查config.json是否存在
if [ ! -f "config.json" ]; then
    echo "错误: config.json不存在"
    exit 1
fi

echo "检查配置文件..."
echo "✓ config.json存在"

# 创建输出目录
if [ ! -d "output" ]; then
    mkdir -p output
    echo "✓ 创建output目录"
fi

# 检查是否已经有容器在运行
CONTAINER_NAME="naps-report-generator"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "发现已存在的容器，正在删除..."
    docker rm -f ${CONTAINER_NAME}
fi

echo ""
echo "构建Docker镜像..."
docker build -t ${CONTAINER_NAME} .

echo ""
echo "启动Docker容器..."
# Docker Desktop on Windows 可以直接访问 Windows 文件系统
# 将项目目录挂载到容器中
docker run -d \
    --name ${CONTAINER_NAME} \
    -p 7861:7860 \
    -v "$(pwd)/config.json:/app/config.json" \
    -v "$(pwd)/output:/app/output" \
    -v "C:\\Users\\sherry\\project:/app/project:ro" \
    --add-host=host.docker.internal:host-gateway \
    --restart unless-stopped \
    ${CONTAINER_NAME}

echo ""
echo "==================================="
echo "启动成功！"
echo "==================================="
echo ""
echo "访问地址: http://localhost:7861"
echo "项目目录: C:\\Users\\sherry\\project"
echo ""
echo "提示: 将你的Git项目放在 C:\\Users\\sherry\\project 目录下"
echo ""
echo "查看日志: docker logs -f ${CONTAINER_NAME}"
echo "停止服务: docker stop ${CONTAINER_NAME}"
echo "重启服务: docker restart ${CONTAINER_NAME}"
echo "删除容器: docker rm -f ${CONTAINER_NAME}"
echo ""
