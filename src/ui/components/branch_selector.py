"""项目/分支选择器——周报、日报共用的 UI 组件

抽取自原周报/日报 tab 里重复的「项目下拉 → 分支多选 → 添加 → 已选列表」交互。
调用方把返回的 selected_state 接到「生成」按钮即可；current_project 供「刷新项目」按钮用。
"""
import gradio as gr


def create_branch_selector(service):
    """构建项目/分支选择器并绑定交互。

    Args:
        service: 提供 get_projects() / get_branches(project) 的服务（ReportService / DailyReportService）

    Returns:
        dict: current_project, selected_branches, selected_count, selected_state
    """
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
    selected_state = gr.State([])

    def _on_add(selected_list, current_proj, branches):
        if not current_proj or not branches:
            return selected_list, gr.update(), selected_list
        new_entries = [f"{current_proj}/{b}" for b in branches]
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

    return {
        "current_project": current_project,
        "selected_branches": selected_branches,
        "selected_count": selected_count,
        "selected_state": selected_state,
    }
