#!/bin/bash

echo "==================================="
echo "  NAPS Git Weekly Report Generator"
echo "==================================="
echo ""

IMAGE_NAME="naps-report-generator"
CONTAINER_NAME="report-generator"

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
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "发现已存在的容器，正在删除..."
    docker rm -f ${CONTAINER_NAME}
fi

echo ""
echo "构建Docker镜像..."
docker build -t ${IMAGE_NAME} .

echo ""
echo "启动Docker容器..."

# 关键修复：使用正确的 Windows 路径
WIN_PROJECT_PATH="C:\\Users\\sherry\\project\\naps_report_generator"
WIN_BASE_PATH="C:\\Users\\sherry\\project"

echo "Windows项目路径: $WIN_PROJECT_PATH"

# 确保输出目录在 Windows 下也存在
mkdir -p "/mnt/c/Users/sherry/project/naps_report_generator/output"

# 复制当前配置文件到 Windows 路径（如果需要）
if [ ! -f "/mnt/c/Users/sherry/project/naps_report_generator/config.json" ]; then
    echo "复制配置文件到 Windows 路径..."
    cp config.json "/mnt/c/Users/sherry/project/naps_report_generator/"
fi

docker run -d \
    --name ${CONTAINER_NAME} \
    -p 7861:7860 \
    -v "${WIN_PROJECT_PATH}\\config.json:/app/config.json" \
    -v "${WIN_PROJECT_PATH}\\output:/app/output" \
    -v "${WIN_BASE_PATH}:/app/project:ro" \
    --add-host=host.docker.internal:host-gateway \
    --restart unless-stopped \
    ${IMAGE_NAME}

if [ $? -eq 0 ]; then
    echo ""
    echo "==================================="
    echo "启动成功！"
    echo "==================================="
    echo ""
    echo "访问地址: http://localhost:7861"
    echo "项目目录: C:\\Users\\sherry\\project"
    echo "配置文件: C:\\Users\\sherry\\project\\naps_report_generator\\config.json"
    echo ""
    echo "查看日志: docker logs -f ${CONTAINER_NAME}"
    echo "停止服务: docker stop ${CONTAINER_NAME}"
    echo "重启服务: docker restart ${CONTAINER_NAME}"
    echo "删除容器: docker rm -f ${CONTAINER_NAME}"
    echo ""
else
    echo "启动失败！"
    exit 1
fi