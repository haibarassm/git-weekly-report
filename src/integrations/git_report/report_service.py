"""Git 周报生成服务 - 业务逻辑层"""
import json
import re
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .git_utils import GitUtils
from .commit_processor import process_commits

# 导入 core 模块（添加项目根目录到路径）
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.workflow.graph import ContentGenerationWorkflow
from src.core.llm.client import get_llm_client
from config import config

logger = logging.getLogger(__name__)


class ReportService:
    """周报生成服务

    负责所有业务逻辑：项目扫描、分支获取、commit 收集、报告生成
    """

    def __init__(self):
        self.git_utils = GitUtils()
        self.author = config.get_author()
        self.output_dir = Path(config.get_output_dir())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.base_dir = Path(os.getenv("PROJECT_BASE_DIR", "C:\\Users\\sherry\\project"))
        self.workflow = ContentGenerationWorkflow(max_iteration=3)

    def get_projects(self) -> list[str]:
        """扫描基础目录下的所有 Git 项目"""
        if not self.base_dir.exists():
            return []

        logger.info(f"开始扫描项目目录: {self.base_dir}")
        projects = []
        max_depth = 3
        checked_count = 0
        max_checks = 100

        def is_git_repo(path):
            return os.path.exists(os.path.join(path, '.git'))

        try:
            for root, dirs, files in os.walk(self.base_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {
                    'node_modules', '__pycache__', 'venv', '.venv',
                    'env', 'dist', 'build', 'target', 'bin', 'obj'
                }]

                try:
                    rel_path = Path(root).relative_to(self.base_dir)
                    depth = len(rel_path.parts)
                except ValueError:
                    continue

                if depth > max_depth:
                    dirs[:] = []
                    continue

                if checked_count >= max_checks:
                    break

                checked_count += 1
                try:
                    if is_git_repo(root):
                        name = str(rel_path).replace('\\', '/')
                        if name == '.':
                            name = self.base_dir.name
                        if name:
                            projects.append(name)
                            logger.info(f"找到项目: {name}")
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"扫描项目目录时出错: {e}")

        logger.info(f"扫描完成，找到 {len(projects)} 个项目")
        return sorted(projects) if projects else []

    def get_branches(self, project_name: str) -> list[str]:
        """获取指定项目的分支列表"""
        if not project_name:
            return []

        try:
            project_path = self._resolve_project_path(project_name)
            if not self.git_utils.validate_repo(str(project_path)):
                return []
            return self.git_utils.get_branches(str(project_path))
        except Exception as e:
            logger.error(f"获取分支失败: {e}")
            return []

    def resolve_path(self, project_name: str) -> Path:
        """解析项目路径"""
        return self._resolve_project_path(project_name)

    def generate_report(
        self,
        selected_branches: list[str],
        days: int,
        mode: str,
    ) -> tuple[str, Optional[Path]]:
        """生成周报/简历

        Args:
            selected_branches: 已选择的分支列表（格式：项目路径/分支名）
            days: 近几天
            mode: simple 或 professional

        Returns:
            (报告内容, 文件路径) 或 (错误信息, None)
        """
        if not selected_branches:
            return "请先添加项目和分支", None

        # 1. 解析分支信息
        branch_info = self._parse_branches(selected_branches)

        # 2. 收集 commits
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        all_commits = self._collect_commits(branch_info, start_date, end_date)

        if not all_commits:
            return f"该时间段内没有找到来自 {self.author} 的提交记录。", None

        # 3. 处理 commits（传入 LLM 客户端用于 summary 生成）
        llm_client = get_llm_client()
        processed_commits = process_commits(all_commits, llm_client=llm_client)
        if not processed_commits:
            return "过滤后没有有效的提交记录。", None

        # 4. 生成报告
        input_content = json.dumps(processed_commits, ensure_ascii=False, indent=2)
        report_content = self.workflow.run(input_text=input_content, mode=mode)

        if not report_content:
            return "生成失败，请检查日志。", None
        logger.info("workflow 返回结果 (前200字符): %s", report_content[:200])

        # 安全网：如果 workflow 返回的是 reviewer JSON，提取 optimized_content
        report_content = self._strip_json_wrapper(report_content)
        # 5. 后处理
        report_content = self._post_process(report_content, mode)

        # 6. 保存
        filepath = self._save_report(report_content, mode)

        return report_content, filepath

    # ---- 私有方法 ----

    def _resolve_project_path(self, project_name: str) -> Path:
        """解析项目路径"""
        if project_name == self.base_dir.name:
            return self.base_dir
        return self.base_dir / project_name

    def _parse_branches(self, selected_branches: list[str]) -> dict[str, list[str]]:
        """解析分支选择列表为 {项目: [分支]} 的映射"""
        branch_info = {}
        for entry in selected_branches:
            parts = entry.rsplit('/', 1)
            if len(parts) == 2:
                project, branch = parts
                branch_info.setdefault(project, []).append(branch)
        return branch_info

    def _collect_commits(
        self,
        branch_info: dict[str, list[str]],
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """从所有项目/分支收集 commits"""
        all_commits = []
        for project_name, branch_list in branch_info.items():
            project_path = self._resolve_project_path(project_name)
            if not self.git_utils.validate_repo(str(project_path)):
                logger.warning(f"无效的Git仓库: {project_path}")
                continue
            for branch in branch_list:
                commits = self.git_utils.get_commits(
                    str(project_path), branch, start_date, end_date, self.author
                )
                for c in commits:
                    c['project'] = project_name
                    c['branch'] = branch
                all_commits.extend(commits)
        return all_commits

    def _strip_json_wrapper(self, content: str) -> str:
        """安全网：如果内容是 reviewer JSON，提取 optimized_content"""
        stripped = content.strip()
        if not stripped.startswith("{"):
            return content
        try:
            result = json.loads(stripped)
            if isinstance(result, dict) and "optimized_content" in result:
                extracted = result["optimized_content"]
                if extracted and isinstance(extracted, str):
                    logger.info("从 reviewer JSON 中提取了 optimized_content")
                    return extracted
        except json.JSONDecodeError:
            pass
        return content

    def _post_process(self, content: str, mode: str) -> str:
        """后处理：根据模式进行修正"""
        if mode == "simple":
            content = self._ensure_next_week_plan(content)
        return content

    def _ensure_next_week_plan(self, content: str) -> str:
        """确保简约模式下下周计划包含所有对接中/已提测的功能"""
        this_week_match = re.search(r'本周工作内容\s*\n([\s\S]*?)(?=\n下周工作内容|\Z)', content)
        if not this_week_match:
            return content

        this_week_text = this_week_match.group(1)
        pending_items = re.findall(r'[、．.]\s*(.+?)\((?:对接中|已提测)\)', this_week_text)
        if not pending_items:
            return content

        next_week_match = re.search(r'下周工作内容\s*\n([\s\S]*)', content)
        if next_week_match:
            next_week_text = next_week_match.group(1)
            missing = [item for item in pending_items if item not in next_week_text]
        else:
            missing = pending_items

        if not missing:
            return content

        next_num = 1
        if next_week_match:
            existing_nums = re.findall(r'(\d+)[、．.]', next_week_match.group(1))
            if existing_nums:
                next_num = max(int(n) for n in existing_nums) + 1

        extra_lines = [f"{next_num + i}、计划发布{item}" for i, item in enumerate(missing)]
        extra_text = "\n".join(extra_lines)

        if next_week_match:
            old_next = next_week_match.group(1).rstrip()
            if not old_next.strip() or '无' in old_next:
                content = re.sub(
                    r'下周工作内容\s*\n[\s\S]*',
                    f'下周工作内容\n{extra_text}',
                    content
                )
            else:
                content = re.sub(
                    r'(下周工作内容\s*\n[\s\S]*)',
                    lambda m: m.group(1).rstrip() + "\n" + extra_text,
                    content
                )
        else:
            content = content.rstrip() + f"\n\n下周工作内容\n{extra_text}"

        return content

    def _save_report(self, content: str, mode: str) -> Path:
        """保存报告到文件"""
        date_str = datetime.now().strftime("%Y%m%d")
        mode_suffix = f"_{mode}" if mode != "simple" else ""
        filename = f"周报_{date_str}{mode_suffix}.md"

        metadata = f"""# Git 周报

**模式**: {mode}
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{content}
"""
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(metadata)

        return filepath
