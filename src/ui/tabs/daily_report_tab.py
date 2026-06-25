"""日报生成 Tab - 复用周报管线，日报专属规则（无状态枚举/不限条数/合并同模块）"""
import logging

import gradio as gr

from integrations.daily_report.daily_report_service import DailyReportService


def create_daily_report_tab(config):
    """创建日报生成 Tab"""
    service = DailyReportService(config)

    with gr.Row():
        # 左列：项目/分支选择 + 时间范围 + 生成
        with gr.Column(scale=1):
            gr.Markdown("### 选择项目")
            current_project = gr.Dropdown(
                label="当前项目",
                choices=service.get_projects(),
                interactive=True,
            )

            gr.Markdown("### 选择分支")
            current_branches = gr.Dropdown(
                label="当前项目的分支（输入搜索，可多选）",
                choices=[],
                interactive=True,
                multiselect=True,
                allow_custom_value=False,
                filterable=True,
            )
            add_btn = gr.Button("➕ 添加到列表", variant="primary", size="sm")

            gr.Markdown("---")
            gr.Markdown("### 已选择")
            selected_branches = gr.CheckboxGroup(
                label="已选择（取消勾选即移除）",
                choices=[],
                interactive=True,
            )
            selected_count = gr.Markdown("**已选择**: 0 个项目/分支")

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

    # 隐藏状态
    selected_state = gr.State([])

    def _on_add(selected_list, current_proj, current_branches):
        if not current_proj or not current_branches:
            return selected_list, gr.update(), selected_list
        new_entries = [f"{current_proj}/{b}" for b in current_branches]
        combined = list(selected_list) if selected_list else []
        for entry in new_entries:
            if entry not in combined:
                combined.append(entry)
        count = len(combined)
        return (
            gr.update(choices=combined, value=combined),
            gr.update(value=f"**已选择**: {count} 个项目/分支"),
            combined,
        )

    def _on_remove(selected_list):
        count = len(selected_list) if selected_list else 0
        return (
            gr.update(value=selected_list),
            gr.update(value=f"**已选择**: {count} 个项目/分支"),
            selected_list if selected_list else [],
        )

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

    # 事件绑定
    current_project.change(
        fn=lambda proj: gr.update(choices=service.get_branches(proj), value=None),
        inputs=[current_project],
        outputs=[current_branches],
    )

    add_btn.click(
        fn=_on_add,
        inputs=[selected_state, current_project, current_branches],
        outputs=[selected_branches, selected_count, selected_state],
    )

    selected_branches.change(
        fn=_on_remove,
        inputs=[selected_branches],
        outputs=[selected_branches, selected_count, selected_state],
    )

    generate_btn.click(
        fn=_on_generate,
        inputs=[selected_state, days],
        outputs=[output, download_file],
    )

    return [current_project, selected_branches, days, output, download_file]
