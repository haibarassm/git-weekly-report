#!/bin/bash
set -e

echo "==================================="
echo "  NAPS Git Weekly Report Generator"
echo "  启动前检查"
echo "==================================="

# 1. 运行测试
echo ""
echo "[1/2] 运行测试用例..."
python -m pytest tests/ -v --tb=short 2>&1
TEST_EXIT=$?

if [ $TEST_EXIT -ne 0 ]; then
    echo ""
    echo "❌ 测试失败，请修复后再启动"
    exit $TEST_EXIT
fi

echo ""
echo "✅ 所有测试通过"
echo ""

# 2. 启动应用
echo "[2/2] 启动 Gradio 服务..."
exec python -m src.ui.gradio_server
