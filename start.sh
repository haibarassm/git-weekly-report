#!/bin/bash

echo "==================================="
echo "  NAPS Git Weekly Report Generator"
echo "==================================="
echo ""

# 获取 Git 分支名称
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
VERSION=${1:-"v0.2"}

# 使用分支名和版本作为标签
IMAGE_NAME="naps-report-generator:${BRANCH_NAME}-${VERSION}"
LATEST_IMAGE_NAME="naps-report-generator:latest"
CONTAINER_NAME="report-generator"

echo "当前分支: $BRANCH_NAME"
echo "镜像标签: $IMAGE_NAME"
echo "最新标签: $LATEST_IMAGE_NAME"
echo ""

# 禁用 Git Bash 路径转换
export MSYS_NO_PATHCONV=1

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
docker tag ${IMAGE_NAME} ${LATEST_IMAGE_NAME}

echo ""
echo "启动Docker容器..."

# Windows 路径（在 Git Bash 中不需要额外转义）
WIN_PROJECT_PATH="C:\\Users\\sherry\\project\\naps_report_generator"
WIN_BASE_PATH="C:\\Users\\sherry\\project"

echo "项目路径: $WIN_PROJECT_PATH"

docker run -d \
    --name ${CONTAINER_NAME} \
    -p 7861:7860 \
    -v "${WIN_PROJECT_PATH}\\config.json:/app/config.json" \
    -v "${WIN_PROJECT_PATH}\\output:/app/output" \
    -v "${WIN_BASE_PATH}:/app/project:ro" \
    -e PROJECT_BASE_DIR=/app/project \
    --add-host=host.docker.internal:host-gateway \
    --restart unless-stopped \
    ${LATEST_IMAGE_NAME}

if [ $? -eq 0 ]; then
    echo ""
    echo "==================================="
    echo "启动成功！"
    echo "==================================="
    echo ""
    echo "访问地址: http://localhost:7861"
    echo "当前分支: $BRANCH_NAME"
    echo "镜像标签: $IMAGE_NAME"
    echo "项目目录: C:\\Users\\sherry\\project"
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
