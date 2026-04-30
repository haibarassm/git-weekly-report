#!/bin/bash

echo "==================================="
echo "  NAPS 生成工具集 V0.7"
echo "==================================="
echo ""

# 获取 Git 分支名称
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
VERSION=${1:-"v0.7"}

# 使用分支名和版本作为标签
IMAGE_NAME="naps-generator:${BRANCH_NAME}-${VERSION}"
LATEST_IMAGE_NAME="naps-generator:latest"
CONTAINER_NAME="naps-generator"

echo "当前分支: $BRANCH_NAME"
echo "镜像标签: $IMAGE_NAME"
echo "最新标签: $LATEST_IMAGE_NAME"
echo ""

# 禁用 Git Bash 路径转换
export MSYS_NO_PATHCONV=1

# 配置目录（用户自定义）
export NAPS_CONFIG_DIR="${NAPS_CONFIG_DIR:-$HOME/.naps}"
export NAPS_PROJECTS_DIR="${NAPS_PROJECTS_DIR:-$HOME/projects}"

# 检查配置文件
if [ ! -f "$NAPS_CONFIG_DIR/naps.json" ]; then
    echo "错误: 配置文件不存在 $NAPS_CONFIG_DIR/naps.json"
    echo "请先创建配置文件，或运行: cp config/naps.json.example ~/.naps/naps.json"
    exit 1
fi

echo "检查配置文件..."
echo "✓ naps.json 存在: $NAPS_CONFIG_DIR/naps.json"
echo "✓ 项目目录: $NAPS_PROJECTS_DIR"

# 创建输出目录
if [ ! -d "output" ]; then
    mkdir -p output
    echo "✓ 创建 output 目录"
fi

# 检查是否已经有容器在运行
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "发现已存在的容器，正在删除..."
    docker rm -f ${CONTAINER_NAME}
fi

echo ""
echo "构建 Docker 镜像..."
docker build -t ${IMAGE_NAME} -t ${LATEST_IMAGE_NAME} .

echo ""
echo "启动 Docker 容器..."

# Windows 路径转换（手动处理）
WIN_CONFIG_PATH="C:\\Users\\sherry\\.naps"
WIN_PROJECTS_PATH="C:\\Users\\sherry\\projects"
WIN_OUTPUT_PATH="C:\\Users\\sherry\\project\\naps_report_generator\\output"

echo "配置目录: $WIN_CONFIG_PATH"
echo "项目目录: $WIN_PROJECTS_PATH"

docker run -d \
    --name ${CONTAINER_NAME} \
    -p 7861:7860 \
    -v "${WIN_CONFIG_PATH}\\naps.json:/app/config/naps.json:ro" \
    -v "${WIN_CONFIG_PATH}\\projects.json:/app/config/projects.json:ro" \
    -v "${WIN_PROJECTS_PATH}:/app/projects:ro" \
    -v "${WIN_OUTPUT_PATH}:/app/output" \
    -e NAPS_CONFIG_PATH=/app/config/naps.json \
    -e NAPS_PROJECTS_PATH=/app/config/projects.json \
    -e LANGCHAIN_API_KEY="${LANGCHAIN_API_KEY}" \
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
    echo ""
    echo "配置目录: $NAPS_CONFIG_DIR"
    echo "项目目录: $NAPS_PROJECTS_DIR"
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
