"""报告生成模块"""
from datetime import datetime
from pathlib import Path
from typing import Optional

# 支持直接运行和模块导入
try:
    from .config import config
    from .git_utils import GitUtils
    from .llm_client import create_llm_client

except ImportError:
    from config import config
    from git_utils import GitUtils
    from llm_client import create_llm_client


class ReportGenerator:
    """周报生成器"""

    def __init__(self):
        """初始化报告生成器"""
        self.git_utils = GitUtils()
        self.llm_client = create_llm_client(config.get_llm_config())
        self.output_dir = config.get_output_dir()
        self.author = config.get_author()
        self.system_prompt_path = Path(__file__).parent / "prompt" / "system_prompt.txt"
        self.user_prompt_path = Path(__file__).parent / "prompt" / "user_prompt.txt"

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        repo_path: str,
        branches: list | str,
        start_date: datetime,
        end_date: datetime,
    ) -> tuple[str, str]:
        """
        生成周报

        Args:
            repo_path: Git仓库路径
            branches: 分支名称列表（支持多分支）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            (报告内容, 报告文件路径)
        """
        # 验证仓库
        if not self.git_utils.validate_repo(repo_path):
            raise ValueError(f"无效的Git仓库: {repo_path}")

        # 兼容单个分支字符串
        if isinstance(branches, str):
            branches = [branches]

        # 获取所有分支的提交记录（使用配置中的author进行筛选）
        all_commits = []
        for branch in branches:
            commits = self.git_utils.get_commits(repo_path, branch, start_date, end_date, self.author)
            # 为每个提交添加分支信息
            for commit in commits:
                commit['branch'] = branch
            all_commits.extend(commits)

        if not all_commits:
            return f"该时间段内没有找到来自 {self.author} 的提交记录。", ""

        # 按分支分组，然后按时间排序
        from collections import defaultdict
        commits_by_branch = defaultdict(list)
        for commit in all_commits:
            commits_by_branch[commit['branch']].append(commit)

        # 按分支顺序（保持用户选择的顺序）
        ordered_commits = []
        for branch in branches:
            if branch in commits_by_branch:
                # 每个分支内的提交按时间排序
                branch_commits = sorted(commits_by_branch[branch], key=lambda x: x['date'], reverse=True)
                ordered_commits.extend(branch_commits)

        # 格式化提交记录（按分支分组）
        commits_text = self._format_commits_by_branch(ordered_commits)

        # 读取提示词
        system_prompt = self._read_prompt(self.system_prompt_path)
        user_prompt = self._read_prompt(self.user_prompt_path).replace("{commits}", commits_text)

        # 调用LLM生成报告
        llm_config = config.get_llm_config()
        report_content = self.llm_client.generate(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 2000),
        )

        # 保存报告
        branch_str = "_".join(branches) if len(branches) <= 3 else f"{len(branches)}branches"
        report_path = self._save_report(report_content, repo_path, branch_str, start_date, end_date)

        return report_content, str(report_path)

    def _read_prompt(self, prompt_path: Path) -> str:
        """读取提示词文件"""
        if not prompt_path.exists():
            raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _format_commits_by_branch(self, commits: list) -> str:
        """按分支分组格式化提交记录"""
        from collections import defaultdict

        # 按分支分组
        commits_by_branch = defaultdict(list)
        for commit in commits:
            branch = commit.get('branch', 'unknown')
            commits_by_branch[branch].append(commit)

        # 格式化输出
        lines = []
        for branch, branch_commits in commits_by_branch.items():
            lines.append(f"\n## 分支: {branch}")
            lines.append(f"共 {len(branch_commits)} 条提交\n")
            for commit in branch_commits:
                lines.append(f"[{commit['date']}] {commit['message']}\n")

        return "\n".join(lines)

    def _save_report(self, content: str, repo_path: str, branch: str, start_date: datetime, end_date: datetime) -> Path:
        """保存报告到文件"""
        # 生成文件名
        repo_name = Path(repo_path).name
        date_str = start_date.strftime("%Y%m%d")
        filename = f"{repo_name}_{branch}_{date_str}_周报.md"
        filepath = self.output_dir / filename

        # 添加元数据
        metadata = f"""# 周报

**作者**: {self.author}
**仓库**: {repo_path}
**分支**: {branch}
**时间范围**: {start_date.strftime("%Y-%m-%d")} ~ {end_date.strftime("%Y-%m-%d")}
**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{content}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(metadata)

        return filepath
