"""Git 周报生成服务 - 业务逻辑层"""
import json
import re
import os
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# 使用共享的 Git 模块
import sys
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.git import CommitFetcher, CommitFilter, TaskClassifier, CommitSplitter, CommitAggregator
from src.core.workflow.graph import ContentGenerationWorkflow
from src.core.llm.client import get_llm_client
from config import config

logger = logging.getLogger(__name__)

# 东八区：容器跑 UTC，但 commit 时间戳和用户都在 +0800；
# 时间窗口必须按东八区算，否则 days=1 会把当天上午的提交切掉
CN_TZ = timezone(timedelta(hours=8))


class ReportService:
    """周报生成服务

    负责所有业务逻辑：项目扫描、分支获取、commit 收集、报告生成
    """

    def __init__(self):
        self.fetcher = CommitFetcher()
        self.filter = CommitFilter()
        self.classifier = TaskClassifier()
        self.splitter = CommitSplitter()
        self.aggregator = CommitAggregator()
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
            from git import Repo
            project_path = self._resolve_project_path(project_name)
            if not project_path.exists():
                return []
            repo = Repo(str(project_path))
            branches = set()
            for head in repo.heads:
                branches.add(head.name)
            for ref in repo.remote().refs:
                branch_name = ref.name.replace('origin/', '', 1)
                if branch_name.startswith('refs/heads/'):
                    branch_name = branch_name.replace('refs/heads/', '', 1)
                elif branch_name.startswith('refs/tags/'):
                    branch_name = branch_name.replace('refs/tags/', '', 1)
                branches.add(branch_name)
            return sorted(list(branches))
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
        end_date = datetime.now(CN_TZ)  # 东八区，对齐 commit 时间戳
        start_date = end_date - timedelta(days=days)
        all_commits = self._collect_commits(branch_info, start_date, end_date)

        if not all_commits:
            return f"该时间段内没有找到来自 {self.author} 的提交记录。", None

        # 3. 处理 commits（使用共享的 Git 模块）
        # 步骤1: 过滤
        filtered_commits, filter_stats = self.filter.filter_commits(all_commits)
        logger.info(f">>> [过滤] 保留 {len(filtered_commits)} 条")

        # 步骤2: 分类
        classified_commits = self.classifier.classify_commits(filtered_commits)

        # 步骤3: 拆分
        llm_client = get_llm_client()
        split_commits = self.splitter.split_commits(classified_commits, llm_client)

        # 步骤4: 聚合
        processed_commits = self.aggregator.aggregate(split_commits, llm_client)

        # 按 scope 合并同模块（日报 + 周报简约共用），防止同模块拆行、多分支内容丢失
        if mode in ("daily", "simple"):
            processed_commits = self._group_by_scope(processed_commits)

        if not processed_commits:
            return "过滤后没有有效的提交记录。", None

        # 4. 生成报告
        if mode in ("daily", "simple"):
            period = "今日" if mode == "daily" else "本周"
            input_content = f"{period}共有 {len(processed_commits)} 个模块的提交，请确保每个模块的工作都覆盖到，不要省略任何一个模块：\n" + json.dumps(processed_commits, ensure_ascii=False, indent=2)
        else:
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
            if not project_path.exists():
                logger.warning(f"无效的Git仓库: {project_path}")
                continue
            for branch in branch_list:
                commits = self.fetcher.fetch(
                    repo_path=str(project_path),
                    branch=branch,
                    author=self.author,
                    since=start_date
                )
                for c in commits:
                    c['project'] = project_name
                    c['branch'] = branch
                all_commits.extend(commits)
        return all_commits

    def _group_by_scope(self, items: list) -> list:
        """日报专用：按 scope(模块) 合并，每个模块一条；过滤「合并分支」类噪声。

        aggregator 输出可能含多个相同 scope 的项（如 3 条 card），日报要求每个模块一行，
        交给 LLM 合并不可靠（会拆行/改名），所以在进 workflow 前用代码按 scope 归并：
        - scope 作为模块名原样使用（carusell / caruselltpay 不会被混成一个）
        - 同 scope 的 tasks 合并到一起
        - 过滤掉「合并远程跟踪分支」这类 merge 噪声 task；全被过滤的 scope 丢弃
        """
        merge_pat = re.compile(r"合并.*(分支|remote|tracking|origin)|merge\s+branch|更新本地分支|抓取远程|拉取.*代码|更新分支.*历史|同步.*远程", re.IGNORECASE)
        # default / 空 scope 通常是 merge、chore、git 操作噪声，整块丢弃
        noise_scopes = {"default", ""}
        grouped: dict = {}
        order: list = []
        for it in items:
            scope = (it.get("scope") or it.get("module") or "").strip()
            if scope in noise_scopes:
                continue
            tasks = [str(t) for t in (it.get("tasks") or []) if not merge_pat.search(str(t))]
            if scope not in grouped:
                grouped[scope] = {"type": it.get("type", ""), "scope": scope, "tasks": []}
                order.append(scope)
            grouped[scope]["tasks"].extend(tasks)
        result = []
        for s in order:
            g = grouped[s]
            if not g["tasks"]:
                continue
            g["task_count"] = len(g["tasks"])
            result.append(g)
        return result

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
        # 先清理禁止的章节和引导词
        content = self._strip_forbidden_sections(content)

        # 日报不做周报专属后处理（状态格式、下周计划等），清理后直接返回
        if mode == "daily":
            return content

        if mode == "simple":
            content = self._ensure_next_week_plan(content)
            content = self._fix_format_issues(content)
        return content

    def _fix_format_issues(self, content: str) -> str:
        """修复格式问题"""
        import re

        # 1. 去掉标题后的 **
        content = re.sub(r'^(本周工作内容|下周工作内容)\*\*\s*$', r'\1', content, flags=re.MULTILINE)

        # 2. 将 1. 替换为 1、（只在工作内容区域）
        lines = []
        in_work_section = False
        for line in content.split('\n'):
            stripped = line.strip()

            # 检测工作内容区域
            if stripped.startswith('本周工作内容') or stripped.startswith('下周工作内容'):
                in_work_section = True

            # 在工作内容区域内，替换序号格式
            if in_work_section and stripped and re.match(r'^\d+\.\s', stripped):
                line = re.sub(r'^(\d+)\.\s+', r'\1、', line)

            lines.append(line)

        content = '\n'.join(lines)

        # 3. 去掉方括号
        content = re.sub(r'\[([^\]]+)\]', r'\1', content)

        # 4. 修复状态格式（提测）→(已提测)
        content = re.sub(r'\(提测\)', '(已提测)', content)

        return content

    def _strip_forbidden_sections(self, content: str) -> str:
        """清理禁止的章节和引导词"""
        lines = []
        skip_until_empty_line = False

        forbidden_prefixes = [
            "根据提供的数据",
            "根据给出的数据",
            "以下是根据",
            "我将生成",
            "以下是",
            "如下所示",
            "为您生成",
        ]

        forbidden_headers = [
            "本周总结",
            "下周总结",
            "总结",
            "本周任务详细信息",
            "下周任务详细信息",
            "详细任务",
            "任务详细信息",
            "本周未发布任务",
            "下周工作计划",  # 应该是"下周工作内容"
            "发布状态",  # 禁止
            "**第",  # 禁止 "**第 1 周" 这种格式
        ]

        for line in content.split('\n'):
            stripped = line.strip()

            # 检查是否是禁止的引导词
            if any(stripped.startswith(p) for p in forbidden_prefixes):
                continue

            # 检查是否是禁止的章节标题
            if any(stripped == h or stripped.startswith(h) for h in forbidden_headers):
                # 跳过这一行，并跳过直到空行
                skip_until_empty_line = True
                continue

            # 跳过"第 X 周"格式
            if re.match(r'^\*?\*?\s*第\s*\d+\s*周', stripped):
                skip_until_empty_line = True
                continue

            # 跳过表格行
            if '|' in stripped and stripped.count('|') >= 2:
                skip_until_empty_line = True
                continue

            # 跳过表格分隔符
            if stripped.startswith('|---') or stripped.startswith('| ---'):
                continue

            # 跳过技术细节行
            if "任务类型：" in stripped or "作用域：" in stripped or "原始 commit" in stripped:
                skip_until_empty_line = True
                continue

            # 如果正在跳过，检查是否到达空行
            if skip_until_empty_line:
                if not stripped:
                    skip_until_empty_line = False
                continue

            # 跳过无意义的符号行
            if stripped in ['---', '***', '___']:
                continue

            lines.append(line)

        # 清理后，确保以"本周工作内容"开头
        result = '\n'.join(lines).strip()

        # 如果第一行不是"本周工作内容"，尝试提取
        if not result.startswith("本周工作内容"):
            # 查找"本周工作内容"的位置
            match = re.search(r'(本周工作内容[\s\S]*?)(?=下周工作内容|\Z)', result)
            if match:
                this_week = match.group(1).strip()
                next_week_match = re.search(r'下周工作内容[\s\S]*', result)
                if next_week_match:
                    next_week = next_week_match.group(0).strip()
                    result = f"{this_week}\n\n{next_week}"
                else:
                    result = this_week

        return result

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
        date_str = datetime.now(CN_TZ).strftime("%Y%m%d")  # 东八区日期
        if mode == "daily":
            filename = f"日报_{date_str}.md"
            report_title = "Git 日报"
        else:
            mode_suffix = f"_{mode}" if mode != "simple" else ""
            filename = f"周报_{date_str}{mode_suffix}.md"
            report_title = "Git 周报"

        metadata = f"""# {report_title}

**模式**: {mode}
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{content}
"""
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(metadata)

        return filepath.resolve()
