"""主入口 - NAPS 生成工具集 V0.7"""
import gradio as gr
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config import config
from ui.tabs.weekly_report_tab import create_weekly_report_tab
from ui.tabs.resume_generate_tab import create_resume_generate_tab
from ui.tabs.resume_manage_tab import create_resume_manage_tab


def _setup_langsmith():
    """配置 LangSmith 环境变量"""
    ls_config = config.get_langsmith_config() if hasattr(config, 'get_langsmith_config') else {"enabled": False}
    has_api_key = bool(ls_config.get("api_key"))

    if ls_config.get("enabled") and has_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = ls_config["api_key"]
        os.environ["LANGCHAIN_PROJECT"] = ls_config.get("project", "naps_generator")
        os.environ["LANGCHAIN_ENDPOINT"] = ls_config.get("endpoint", "https://api.smith.langchain.com")
        os.environ["NAPS_VERBOSE_LLM_LOG"] = "false"
        import logging
        logging.getLogger(__name__).info(f"LangSmith 已启用，project={ls_config.get('project')}")
    else:
        os.environ["LANGCHAIN_PROJECT"] = "naps_generator"
        os.environ["NAPS_VERBOSE_LLM_LOG"] = "true"


def launch():
    """启动应用"""
    _setup_langsmith()

    author = config.get_author() if hasattr(config, 'get_author') else "Developer"

    with gr.Blocks(title="NAPS - 生成工具集", theme=gr.themes.Base()) as app:
        gr.Markdown("# 🧾 NAPS 生成工具集 V0.7")
        gr.Markdown(f"**当前用户**: {author}")

        with gr.Tabs():
            with gr.Tab("📊 周报生成"):
                create_weekly_report_tab(config)

            with gr.Tab("📄 简历生成"):
                create_resume_generate_tab(config)

            with gr.Tab("⚙️ 项目管理"):
                create_resume_manage_tab(config)

    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )


if __name__ == "__main__":
    launch()
