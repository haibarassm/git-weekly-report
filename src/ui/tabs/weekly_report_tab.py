"""周报生成 Tab"""
import gradio as gr
from integrations.git_report.report_service import ReportService


def create_weekly_report_tab(config):
    """创建周报生成 Tab"""
    service = ReportService()

    with gr.Row():
        # 左列：项目选择
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
                label="已选择（可取消勾选移除）",
                choices=[],
                interactive=True,
            )
            selected_count = gr.Markdown("**已选择**: 0 个项目/分支")

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

    # 隐藏状态
    selected_state = gr.State([])

    # 事件处理函数
    def _on_add(selected_list, current_proj, current_branches):
        """添加分支"""
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
        """移除分支"""
        count = len(selected_list) if selected_list else 0
        return (
            gr.update(value=selected_list),
            gr.update(value=f"**已选择**: {count} 个项目/分支"),
            selected_list if selected_list else [],
        )

    def _on_generate(selected_branches, days_count, mode_cn, progress=gr.Progress()):
        """生成按钮事件"""
        mode = "simple" if mode_cn == "简约模式" else "professional"

        if not selected_branches:
            return "请先添加项目和分支", None

        try:
            progress(0.2, desc="获取 Git commits...")
            content, filepath = service.generate_report(
                selected_branches=selected_branches,
                days=days_count,
                mode=mode,
            )
            progress(1.0, desc="完成!")
            return content, str(filepath) if filepath else ""
        except Exception as e:
            import logging
            logging.exception("生成失败")
            return f"生成失败: {str(e)}", ""

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
        fn=_on_generate,
        inputs=[selected_state, days, mode],
        outputs=[output, download_file],
    )
