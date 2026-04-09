"""Git 周报内容源"""
from typing import Dict, Any
from datetime import datetime
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.sources.base import ContentSource
from .git_utils import GitUtils
from .commit_processor import process_commits
from config import config
from llm_client import create_llm_client


class GitReportSource(ContentSource):
    """Git 周报内容源

    职责：从 Git commits 获取周报内容
    """

    def __init__(self):
        self.git_utils = GitUtils()
        self.author = config.get_author()

    def fetch(self, repo_path: str, branches: list | str,
             start_date: datetime, end_date: datetime,
             enable_v04: bool = True, **kwargs) -> str:
        """获取 Git commits 并处理为结构化内容

        Args:
            repo_path: Git 仓库路径
            branches: 分支名称列表
            start_date: 开始日期
            end_date: 结束日期
            enable_v04: 是否启用 V0.4 聚合
            **kwargs: 其他参数

        Returns:
            处理后的 JSON 格式内容
        """
        import json

        # 验证仓库
        if not self.git_utils.validate_repo(repo_path):
            raise ValueError(f"无效的Git仓库: {repo_path}")

        # 兼容单个分支字符串
        if isinstance(branches, str):
            branches = [branches]

        # 获取所有分支的提交记录
        all_commits = []
        for branch in branches:
            commits = self.git_utils.get_commits(
                repo_path, branch, start_date, end_date, self.author
            )
            for commit in commits:
                commit['branch'] = branch
            all_commits.extend(commits)

        if not all_commits:
            return f"该时间段内没有找到来自 {self.author} 的提交记录。"

        # 按分支分组，然后按时间排序
        from collections import defaultdict
        commits_by_branch = defaultdict(list)
        for commit in all_commits:
            commits_by_branch[commit['branch']].append(commit)

        ordered_commits = []
        for branch in branches:
            if branch in commits_by_branch:
                branch_commits = sorted(
                    commits_by_branch[branch],
                    key=lambda x: x['date'],
                    reverse=True
                )
                ordered_commits.extend(branch_commits)

        # 使用 V0.5 处理流程
        llm_client = create_llm_client(config.get_llm_config())
        processed_commits = process_commits(
            ordered_commits,
            llm_client=llm_client,
            enable_v04=enable_v04
        )

        # 返回 JSON 格式
        return json.dumps(
            processed_commits,
            ensure_ascii=False,
            indent=2
        )

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        return {
            "source_type": "git_commits",
            "author": self.author,
            "supported_formats": ["json"]
        }
