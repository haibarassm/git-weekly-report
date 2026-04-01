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
    from .commit_processor import process_commits
except ImportError:
    # 直接运行时使用绝对导入
    from git_utils import GitUtils
    from report_generator import ReportGenerator
    from config import config
    from commit_processor import process_commits


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

        import logging
        import os
        from pathlib import Path

        logger = logging.getLogger(__name__)
        logger.info(f"开始扫描项目目录: {self.base_dir}")

        projects = []
        max_depth = 4  # 支持最多4层子目录
        checked_count = 0
        max_checks = 200  # 最多检查200个目录

        # 使用更快的 Git 仓库检测方法
        def is_git_repo_fast(path):
            """快速检测 Git 仓库（只检查 .git 目录是否存在）"""
            git_dir = os.path.join(path, '.git')
            return os.path.exists(git_dir)

        try:
            # 递归扫描目录
            for root, dirs, files in os.walk(self.base_dir):
                # 跳过隐藏目录和常见的非项目目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', 'venv', '.venv',
                    'env', 'dist', 'build', 'target', 'bin', 'obj'
                }]

                # 计算相对深度
                try:
                    rel_path = Path(root).relative_to(self.base_dir)
                    depth = len(rel_path.parts)
                except ValueError:
                    continue

                if depth > max_depth:
                    # 超过最大深度，不再深入
                    dirs[:] = []
                    continue

                if checked_count >= max_checks:
                    logger.warning(f"已达到最大检查数量限制 ({max_checks})，停止扫描")
                    break

                checked_count += 1
                try:
                    if is_git_repo_fast(root):
                        project_name = str(rel_path).replace('\\', '/')
                        projects.append(project_name)
                        logger.info(f"找到项目: {project_name}")
                except Exception as e:
                    logger.debug(f"验证目录失败 {root}: {e}")
                    continue

        except Exception as e:
            logger.error(f"扫描项目目录时出错: {e}")

        logger.info(f"扫描完成，找到 {len(projects)} 个项目")
        return sorted(projects) if projects else []

    def get_branches(self, project_name: str):
        """获取指定项目的分支列表"""
        if not project_name:
            return []

        try:
            # 使用 pathlib.Path 正确处理跨平台路径
            project_path = self.base_dir / project_name
            if not self.git_utils.validate_repo(str(project_path)):
                return []
            branches = self.git_utils.get_branches(str(project_path))
            return branches
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"获取分支失败: {e}, project_name={project_name}, base_dir={self.base_dir}")
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
                # 使用 pathlib.Path 正确处理跨平台路径
                project_path = self.base_dir / project_name

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

            import logging
            logger = logging.getLogger(__name__)

            # V0.3: 对 commits 进行过滤、分类和拆分
            processed_commits = process_commits(all_commits)

            if not processed_commits:
                return f"过滤后没有有效的提交记录。", ""

            # 将项目/分支信息添加回处理后的 commits
            # 需要重新关联原始 commit 的 project 和 branch
            processed_commits = self._restore_project_branch_info(processed_commits, all_commits)

            processed_commits.sort(key=lambda x: (x.get('project', ''), x.get('branch', ''), x.get('date', '')), reverse=True)

            # 格式化为文本
            commits_text = self._format_processed_commits(processed_commits)

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

    def _restore_project_branch_info(self, processed_commits: list, original_commits: list) -> list:
        """
        恢复处理后的 commit 的项目和分支信息
        根据 source_commit (hash) 匹配原始 commit 的 project 和 branch
        """
        # 创建 hash -> (project, branch, date) 的映射
        commit_info = {}
        for commit in original_commits:
            commit_info[commit['hash']] = {
                'project': commit.get('project', ''),
                'branch': commit.get('branch', ''),
                'date': commit.get('date', '')
            }

        # 恢复信息
        for commit in processed_commits:
            source_hash = commit.get('source_commit', '')
            if source_hash in commit_info:
                commit['project'] = commit_info[source_hash]['project']
                commit['branch'] = commit_info[source_hash]['branch']
                commit['date'] = commit_info[source_hash]['date']

        return processed_commits

    def _format_processed_commits(self, commits: list) -> str:
        """
        格式化处理后的 commits（V0.3）
        显示分类信息和拆分后的任务：type, scope, tasks
        """
        from collections import defaultdict

        commits_by_project_branch = defaultdict(list)
        for commit in commits:
            key = f"{commit.get('project', '')}/{commit.get('branch', '')}"
            commits_by_project_branch[key].append(commit)

        lines = []
        for key, branch_commits in commits_by_project_branch.items():
            lines.append(f"共 {len(branch_commits)} 条提交\n")
            for commit in branch_commits:
                commit_type = commit.get('type', 'refactor')
                scope = commit.get('scope', 'default')
                tasks = commit.get('tasks', [])
                # 格式: [type/scope] 任务1; 任务2; ...
                tasks_text = '; '.join(tasks)
                lines.append(f"[{commit_type}/{scope}] {tasks_text}")

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
        """保存报告到文件（只保存纯周报内容）"""
        output_dir = Path(config.get_output_dir())
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = start_date.strftime("%Y%m%d")
        filename = f"周报_{date_str}.txt"
        filepath = output_dir / filename

        # 直接保存LLM生成的内容，不添加任何元数据
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return str(filepath)

    def create_ui(self):
        """创建Gradio界面"""
        with gr.Blocks(title="Git周报生成器",theme=gr.themes.Base()) as app:
            gr.Markdown("# Git周报生成器")
            gr.Markdown(f"**当前用户**: {self.author}")
            gr.Markdown(f"**项目目录**: `{self.base_dir}`")

            with gr.Row():
                # 左列：项目选择
                with gr.Column(scale=1):
                    gr.Markdown("### 选择项目")
                    current_project = gr.Dropdown(
                        label="当前项目",
                        choices=self.get_projects(),
                        interactive=True,
                    )

                    gr.Markdown("### 选择分支")
                    current_branches = gr.CheckboxGroup(
                        label="当前项目的分支（可多选）",
                        choices=[],
                        interactive=True,
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
                    4. 设置天数
                    5. 生成周报
                    """)

                # 中列：时间设置和生成
                with gr.Column(scale=1):
                    gr.Markdown("### 时间范围")
                    days = gr.Slider(
                        label="天数",
                        minimum=1,
                        maximum=30,
                        value=7,
                        step=1,
                    )

                    gr.Markdown("---")

                    gr.Markdown("### 操作")
                    refresh_btn = gr.Button("🔄 刷新项目", size="sm")
                    clear_btn = gr.Button("🗑️ 清空全部", size="sm")

                    gr.Markdown("---")

                    generate_btn = gr.Button("📊 生成周报", variant="primary", size="lg")

                # 右列：输出结果
                with gr.Column(scale=2):
                    output = gr.Textbox(label="周报内容", lines=10)
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

        return app


def create_app():
    """创建Gradio应用实例"""
    print("[DEBUG] Creating ReportApp instance...", flush=True)
    report_app = ReportApp()
    print("[DEBUG] ReportApp created successfully", flush=True)
    print("[DEBUG] Creating UI...", flush=True)
    ui = report_app.create_ui()
    print("[DEBUG] UI created successfully", flush=True)
    return ui


if __name__ == "__main__":
    import os
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=== 开始启动 Gradio 应用 ===")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python 路径: {sys.path}")

    try:
        print("创建应用...")
        app = create_app()
        print("应用创建成功！")

        output_dir = os.path.abspath("output")
        os.makedirs(output_dir, exist_ok=True)
        print(f"输出目录: {output_dir}")

        # 支持容器环境，使用 0.0.0.0 监听所有接口
        server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
        print(f"准备启动服务器: {server_name}:7860")

        app.launch(
            server_name=server_name,
            server_port=7860,
            share=False,
            allowed_paths=[output_dir],
        )
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        raise
