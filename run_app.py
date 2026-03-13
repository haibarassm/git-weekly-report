#!/usr/bin/env python3
"""Gradio应用启动脚本"""
import sys
import os

# 强制禁用输出缓冲
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# 禁用所有可能的外部网络请求
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["DO_NOT_TRACK"] = "1"

# 添加 src 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def log_and_print(msg):
    """同时输出到日志和 stdout"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(msg)
    print(msg, flush=True)

# 导入并运行应用
if __name__ == "__main__":
    from src.app import create_app
    import gradio as gr

    log_and_print("=== 开始启动 Gradio 应用 ===")
    log_and_print(f"当前工作目录: {os.getcwd()}")
    log_and_print(f"Python 路径: {sys.path}")

    try:
        log_and_print("创建应用...")
        app = create_app()
        log_and_print("应用创建成功！")

        output_dir = os.path.abspath("output")
        os.makedirs(output_dir, exist_ok=True)
        log_and_print(f"输出目录: {output_dir}")

        # 支持容器环境，使用 0.0.0.0 监听所有接口
        server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
        server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
        log_and_print(f"准备启动服务器: {server_name}:{server_port}")

        app.launch(
            server_name=server_name,
            server_port=server_port,
            share=False,
            allowed_paths=[output_dir],
            show_error=True,
            quiet=False,
        )
    except Exception as e:
        log_and_print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
