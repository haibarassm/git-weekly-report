"""Gradio应用入口"""
import gradio as gr
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# 支持直接运行和模块导入
try:
    from .git_utils import GitUtils
    from .report_generator import ReportGenerator
    from .config import config
except ImportError:
    # 直接运行时使用绝对导入
    from git_utils import GitUtils
    from report_generator import ReportGenerator
    from config import config


class ReportApp:
    """周报生成应用"""

    def __init__(self):
        """初始化应用"""
        self.git_utils = GitUtils()
        self.report_generator = ReportGenerator()
        self.author = config.get_author()
        # 固定基础目录
        self.base_dir = self._get_base_dir()

    def _get_base_dir(self) -> Path:
        """获取基础目录"""
        base = os.getenv("PROJECT_BASE_DIR", "C:\\Users\\sherry\\project")
        return Path(base)

    def get_projects(self):
        """获取项目列表"""
        if not self.base_dir.exists():
            return []

        projects = []
        for item in self.base_dir.rglob('*'):
            if item.is_dir() and not item.name.startswith('.'):
                try:
                    if self.git_utils.validate_repo(str(item)):
                        relative_path = item.relative_to(self.base_dir)
                        project_name = str(relative_path).replace('\\', '/')
                        projects.append(project_name)
                except Exception:
                    continue

        return sorted(projects) if projects else []

    def get_branches(self, project_name: str):
        """获取指定项目的分支列表"""
        if not project_name:
            return []

        try:
            project_path = self.base_dir / project_name.replace('/', '\\')
            if not self.git_utils.validate_repo(str(project_path)):
                return []
            branches = self.git_utils.get_branches(str(project_path))
            return branches
        except Exception:
            return []

    def add_branches(self, current_selected: list, current_project: str, branches_to_add: list):
        """添加分支到已选择列表"""
        if not current_project or not branches_to_add:
            return current_selected

        # 为每个分支添加项目前缀
        new_entries = [f"{current_project}/{branch}" for branch in branches_to_add]

        # 合并去重
        combined = list(current_selected) if current_selected else []
        for entry in new_entries:
            if entry not in combined:
                combined.append(entry)

        return combined

    def remove_branches(self, current_selected: list, branches_to_remove: list):
        """从已选择列表移除分支"""
        if not current_selected or not branches_to_remove:
            return current_selected

        return [item for item in current_selected if item not in branches_to_remove]

    def generate_report_handler(
        self,
        selected_branches: list,
        days: int,
    ):
        """生成周报处理器"""
        if not selected_branches or len(selected_branches) == 0:
            return "请先添加项目和分支", None

        try:
            # 解析分支信息（格式：项目路径/分支名）
            branch_info = {}
            for branch_with_project in selected_branches:
                # 从右边分割，最后一部分是分支名
                parts = branch_with_project.rsplit('/', 1)
                if len(parts) == 2:
                    project_name, branch_name = parts
                    if project_name not in branch_info:
                        branch_info[project_name] = []
                    branch_info[project_name].append(branch_name)

            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # 收集所有提交记录
            all_commits = []
            for project_name, branch_list in branch_info.items():
                project_path = self.base_dir / project_name.replace('/', '\\')

                if not self.git_utils.validate_repo(str(project_path)):
                    return f"无效的Git仓库: {project_path}", None

                for branch in branch_list:
                    commits = self.git_utils.get_commits(
                        str(project_path), branch, start_date, end_date, self.author
                    )
                    for commit in commits:
                        commit['project'] = project_name
                        commit['branch'] = branch
                    all_commits.extend(commits)

            if not all_commits:
                return f"该时间段内没有找到来自 {self.author} 的提交记录。", ""

            all_commits.sort(key=lambda x: (x['project'], x['branch'], x['date']), reverse=True)

            # 格式化为文本
            commits_text = self._format_commits_by_project_branch(all_commits)

            # 读取提示词
            system_prompt = self._read_prompt()
            user_prompt = self._read_user_prompt().replace("{commits}", commits_text)

            # 调用LLM生成报告
            llm_config = config.get_llm_config()
            from .llm_client import create_llm_client
            llm_client = create_llm_client(llm_config)
            report_content = llm_client.generate(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 2000),
            )

            # 保存报告
            report_path = self._save_report(report_content, start_date, end_date)

            return report_content, report_path

        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            return f"生成报告时出错: {str(e)}\n\n详细错误:\n{error_detail}", None

    def _format_commits_by_project_branch(self, commits: list) -> str:
        """按项目和分支分组格式化提交记录（不显示项目/分支前缀）"""
        from collections import defaultdict

        commits_by_project_branch = defaultdict(list)
        for commit in commits:
            key = f"{commit['project']}/{commit['branch']}"
            commits_by_project_branch[key].append(commit)

        lines = []
        for key, branch_commits in commits_by_project_branch.items():
            lines.append(f"共 {len(branch_commits)} 条提交\n")
            for commit in branch_commits:
                lines.append(f"[{commit['date']}] {commit['message']}")

        return "\n".join(lines)

    def _read_prompt(self) -> str:
        """读取系统提示词"""
        prompt_path = Path(__file__).parent / "prompt" / "system_prompt.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _read_user_prompt(self) -> str:
        """读取用户提示词"""
        prompt_path = Path(__file__).parent / "prompt" / "user_prompt.txt"
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_report(self, content: str, start_date: datetime, end_date: datetime) -> str:
        """保存报告到文件"""
        output_dir = Path(config.get_output_dir())
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = start_date.strftime("%Y%m%d")
        filename = f"周报_{date_str}.md"
        filepath = output_dir / filename

        metadata = f"""# 周报

**作者**: {self.author}
**时间范围**: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{content}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(metadata)

        return str(filepath)

    def create_ui(self):
        """创建Gradio界面"""
        with gr.Blocks(title="Git周报生成器") as app:
            gr.Markdown("# Git周报生成器")
            gr.Markdown(f"**当前用户**: {self.author}")
            gr.Markdown(f"**项目目录**: `{self.base_dir}`")

            with gr.Row():
                with gr.Column(scale=1):
                    # 项目选择区
                    gr.Markdown("### 1. 选择项目")
                    current_project = gr.Dropdown(
                        label="当前项目",
                        choices=self.get_projects(),
                        interactive=True,
                    )

                    # 分支选择区
                    gr.Markdown("### 2. 选择分支")
                    current_branches = gr.CheckboxGroup(
                        label="当前项目的分支（可多选）",
                        choices=[],
                        interactive=True,
                    )

                    # 添加按钮
                    add_btn = gr.Button("➕ 添加到已选列表", variant="primary", size="sm")

                    gr.Markdown("---")

                    # 已选择列表
                    gr.Markdown("### 3. 已选择的项目/分支")
                    selected_branches = gr.CheckboxGroup(
                        label="已选择（可取消勾选移除）",
                        choices=[],
                        interactive=True,
                    )

                    # 时间选择
                    gr.Markdown("### 4. 设置时间范围")
                    days = gr.Slider(
                        label="时间范围（天）",
                        minimum=1,
                        maximum=30,
                        value=7,
                        step=1,
                    )

                    # 操作按钮
                    with gr.Row():
                        refresh_btn = gr.Button("🔄 刷新项目", size="sm")
                        clear_btn = gr.Button("🗑️ 清空全部", size="sm")

                    generate_btn = gr.Button("📊 生成周报", variant="primary", size="lg")

                    # 已选数量显示
                    selected_count = gr.Markdown("**已选择**: 0 个项目/分支")

                with gr.Column(scale=2):
                    output = gr.Markdown(label="周报内容")
                    download_file = gr.File(label="下载周报", visible=True)

            # 隐藏状态
            selected_state = gr.State([])

            # 事件绑定
            def update_branches(project_name):
                """更新当前项目的分支列表"""
                branch_list = self.get_branches(project_name)
                return gr.update(choices=branch_list, value=None)

            def on_add(selected_list, current_proj, current_branches):
                """添加分支到已选择列表"""
                new_selected = self.add_branches(selected_list, current_proj, current_branches)
                count = len(new_selected)
                return (
                    gr.update(choices=new_selected, value=new_selected),  # 更新choices和value
                    gr.update(value=f"**已选择**: {count} 个项目/分支"),
                    new_selected  # 更新状态
                )

            def on_remove(selected_list):
                """移除分支后更新显示和状态"""
                count = len(selected_list) if selected_list else 0
                return (
                    gr.update(value=selected_list),  # 更新value
                    gr.update(value=f"**已选择**: {count} 个项目/分支"),
                    selected_list if selected_list else []  # 更新状态
                )

            def on_clear():
                """清空所有选择"""
                return (
                    gr.update(choices=[], value=None),  # 清空choices和value
                    gr.update(value="**已选择**: 0 个项目/分支"),
                    []  # 清空状态
                )

            def on_refresh():
                """刷新项目列表"""
                return gr.update(choices=self.get_projects(), value=None)

            # 绑定事件
            current_project.change(
                fn=update_branches,
                inputs=[current_project],
                outputs=[current_branches],
            )

            add_btn.click(
                fn=on_add,
                inputs=[selected_state, current_project, current_branches],
                outputs=[selected_branches, selected_count, selected_state],
            )

            selected_branches.change(
                fn=on_remove,
                inputs=[selected_branches],
                outputs=[selected_branches, selected_count, selected_state],
            )

            refresh_btn.click(
                fn=on_refresh,
                outputs=[current_project],
            )

            clear_btn.click(
                fn=on_clear,
                outputs=[selected_branches, selected_count, selected_state],
            )

            generate_btn.click(
                fn=self.generate_report_handler,
                inputs=[selected_state, days],
                outputs=[output, download_file],
            )

            # 使用说明
            gr.Markdown("""
            ## 使用说明

            1. **选择项目** - 从下拉列表选择一个项目
            2. **选择分支** - 勾选该项目需要包含的分支（可多选）
            3. **添加到列表** - 点击"➕ 添加到已选列表"按钮
            4. **重复以上步骤** - 可以继续添加其他项目的分支
            5. **查看已选** - 在"已选择"区域查看所有已选项目/分支
            6. **移除项目** - 在"已选择"中取消勾选即可移除
            7. **设置时间** - 调整时间范围
            8. **生成周报** - 点击"📊 生成周报"按钮

            ## 注意事项

            - 项目目录固定为 `C:\\Users\\sherry\\project`
            - 支持多项目多分支汇总生成周报
            - 仅包含当前用户的提交记录
            """)

        return app


def create_app():
    """创建Gradio应用实例"""
    report_app = ReportApp()
    return report_app.create_ui()


if __name__ == "__main__":
    import os
    app = create_app()
    output_dir = os.path.abspath("output")
    os.makedirs(output_dir, exist_ok=True)

    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        allowed_paths=[output_dir],
    )
