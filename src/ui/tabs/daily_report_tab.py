"""日报生成 Tab - 复用周报管线，日报专属规则（无状态枚举/不限条数/合并同模块）"""
import logging

import gradio as gr

from integrations.daily_report.daily_report_service import DailyReportService
from ui.components import create_branch_selector


def create_daily_report_tab(config):
    """创建日报生成 Tab"""
    service = DailyReportService(config)

    with gr.Row():
        # 左列：项目/分支选择 + 时间范围 + 生成
        with gr.Column(scale=1):
            sel = create_branch_selector(service)
            selected_state = sel["selected_state"]

            gr.Markdown("---")
            gr.Markdown("### 时间范围")
            days = gr.Slider(label="天数（默认当天）", minimum=1, maximum=7, value=1, step=1)

            gr.Markdown("---")
            generate_btn = gr.Button("📊 生成日报", variant="primary", size="lg")

            gr.Markdown("""
            **日报规则**（区别于周报）
            - 无 `(对接中)(已提测)(已发布)` 等状态标注
            - 不限条数：有多少模块写多少
            - 同模块的多个提交合并成一条
            """)

        # 右列：输出
        with gr.Column(scale=2):
            gr.Markdown("### 生成结果")
            output = gr.Textbox(label="日报内容", lines=18)
            download_file = gr.File(label="下载日报")

    def _on_generate(selected_list, days_count, progress=gr.Progress()):
        if not selected_list:
            return "请先添加项目和分支", None
        try:
            progress(0.2, desc="获取 Git commits...")
            content, filepath = service.generate_daily(
                selected_branches=selected_list,
                days=days_count,
            )
            progress(1.0, desc="完成!")
            return content, str(filepath) if filepath else None
        except Exception as e:
            logging.exception("日报生成失败")
            return f"生成失败: {str(e)}", None

    generate_btn.click(
        fn=_on_generate,
        inputs=[selected_state, days],
        outputs=[output, download_file],
    )

    return [sel["current_project"], sel["selected_branches"], days, output, download_file]
