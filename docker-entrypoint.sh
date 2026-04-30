#!/bin/bash

echo "==================================="
echo "  NAPS Git Weekly Report Generator"
echo "  V0.7.1"
echo "==================================="

# 安装可能缺失的包
echo "检查并安装缺失的依赖..."
pip install langchain-ollama langchain-openai --default-timeout=100 || echo "警告: 部分包安装失败"

echo "启动 Gradio 服务..."
echo "访问地址: http://localhost:7860"
echo ""

# 不使用 set -e，即使服务启动失败也继续
python -m src.ui.gradio_server
