"""Gradio UI - 纯前端层"""
import gradio as gr
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from integrations.git_report.report_service import ReportService
from config import config


class ReportAppV06:
    """NAPS 生成工具 - 纯 UI 层"""

    def __init__(self):
        self.service = ReportService()

    # ---- UI 事件处理（薄层，只做数据转换和调用 service）----

    def _on_generate(self, selected_branches: list, days: int, mode_cn: str, progress=gr.Progress()):
        """周报生成按钮事件"""
        mode = "simple" if mode_cn == "简约模式" else "professional"

        if not selected_branches:
            return "请先添加项目和分支", None

        try:
            progress(0.2, desc="获取 Git commits...")
            content, filepath = self.service.generate_report(
                selected_branches=selected_branches,
                days=days,
                mode=mode,
            )
            progress(1.0, desc="完成!")
            return content, str(filepath) if filepath else None
        except Exception as e:
            import logging
            logging.exception("生成失败")
            return f"生成失败: {str(e)}", None

    # ---- UI 构建 ----

    def create_ui(self):
        """创建 Gradio 界面"""
        from ui.tabs.resume_generate_tab import create_resume_generate_tab
        from ui.tabs.daily_report_tab import create_daily_report_tab
        from ui.tabs.resume_manage_tab import create_resume_manage_tab
        from ui.tabs.company_manage_tab import create_company_manage_tab
        service = self.service

        with gr.Blocks(title="NAPS 生成工具", theme=gr.themes.Base()) as app:
            gr.Markdown("# 🧾 NAPS 生成工具")
            gr.Markdown(f"**当前用户**: {service.author} | **项目目录**: `{service.base_dir}`")

            with gr.Tabs():
                with gr.Tab("📊 周报"):
                    (current_project, selected_branches, selected_count, selected_state,
                     days, mode, refresh_btn, clear_btn,
                     generate_btn, output, download_file) = self._build_weekly_tab(service)
                with gr.Tab("📅 日报"):
                    create_daily_report_tab(config)
                with gr.Tab("📄 简历"):
                    with gr.Tabs():
                        with gr.Tab("简历生成"):
                            create_resume_generate_tab(config)
                        with gr.Tab("简历模板管理"):
                            create_resume_manage_tab(config)
                        with gr.Tab("公司管理"):
                            create_company_manage_tab()

            # ---- 事件绑定 ----
            # 注：项目/分支选择器的交互（项目→分支联动、添加、移除）已封装在
            # create_branch_selector 内部，这里只绑周报专属的刷新/清空/生成。

            refresh_btn.click(
                fn=lambda: gr.update(choices=service.get_projects(), value=None),
                outputs=[current_project],
            )

            clear_btn.click(
                fn=lambda: (
                    gr.update(choices=[], value=None),
                    gr.update(value="**已选择**: 0 个项目/分支"),
                    [],
                ),
                outputs=[selected_branches, selected_count, selected_state],
            )

            generate_btn.click(
                fn=self._on_generate,
                inputs=[selected_state, days, mode],
                outputs=[output, download_file],
            )

        return app

    def _build_weekly_tab(self, service):
        """构建周报 tab 的 UI，返回事件绑定需要的组件"""
        from ui.components import create_branch_selector

        with gr.Row():
            # 左列：项目/分支选择（公共组件）
            with gr.Column(scale=1):
                sel = create_branch_selector(service)
                gr.Markdown("---")
                gr.Markdown("""
                **使用说明**
                1. 选择项目
                2. 勾选分支（可多选）
                3. 点击添加
                4. 设置天数和模式
                5. 生成周报
                """)

            # 中列：设置和操作
            with gr.Column(scale=1):
                gr.Markdown("### 时间范围")
                days = gr.Slider(label="天数", minimum=1, maximum=30, value=7, step=1)

                gr.Markdown("---")
                gr.Markdown("### 生成模式")
                mode = gr.Radio(
                    label="模式",
                    choices=["简约模式", "专业模式"],
                    value="简约模式",
                )

                gr.Markdown("---")
                gr.Markdown("### 操作")
                refresh_btn = gr.Button("🔄 刷新项目", size="sm")
                clear_btn = gr.Button("🗑️ 清空全部", size="sm")

                gr.Markdown("---")
                generate_btn = gr.Button("📊 生成周报", variant="primary", size="lg")

            # 右列：输出
            with gr.Column(scale=2):
                output = gr.Textbox(label="周报内容", lines=15)
                download_file = gr.File(label="下载周报", visible=True)

        return (sel["current_project"], sel["selected_branches"], sel["selected_count"],
                sel["selected_state"], days, mode, refresh_btn, clear_btn,
                generate_btn, output, download_file)


def _setup_langsmith():
    """配置 LangSmith 环境变量（LangGraph 自动读取）"""
    from config import config
    import os

    ls_config = config.get_langsmith_config()
    # api_key 优先用 config；为空则走环境变量 LANGCHAIN_API_KEY（避免把密钥写进版本库）
    api_key = ls_config.get("api_key") or os.environ.get("LANGCHAIN_API_KEY", "")

    if ls_config.get("enabled") and api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = api_key
        os.environ["LANGCHAIN_PROJECT"] = ls_config.get("project", "report_generator")
        os.environ["LANGCHAIN_ENDPOINT"] = ls_config.get("endpoint", "https://api.smith.langchain.com")
        # 有 LangSmith 时不需要详细 LLM 日志（LangSmith 已记录）
        os.environ["NAPS_VERBOSE_LLM_LOG"] = "false"
        import logging
        logging.getLogger(__name__).info(f"LangSmith 已启用，project={ls_config.get('project')}")
    else:
        os.environ["LANGCHAIN_PROJECT"] = "report_generator"
        # 无 LangSmith 时开启详细日志方便调试
        os.environ["NAPS_VERBOSE_LLM_LOG"] = "true"


def launch():
    """启动应用"""
    _setup_langsmith()
    app = ReportAppV06()
    ui = app.create_ui()
    ui.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )


if __name__ == "__main__":
    launch()
