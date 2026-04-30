"""Commit 获取器 - 兼容周报（指定天数）和简历（全量）"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from git import Repo


class CommitFetcher:
    """Commit 获取器 - 周报和简历共享"""

    def fetch(
        self,
        repo_path: str,
        branch: str,
        author: str,
        days: Optional[int] = None,
        since: Optional[datetime] = None,
    ) -> List[Dict]:
        """获取 commits

        Args:
            repo_path: 仓库路径
            branch: 分支名
            author: 作者筛选
            days: 最近 N 天（可选，不传则获取全部）
            since: 起始时间（可选，优先级高于 days）

        Returns:
            字典列表，每个字典包含 hash, author, date, message, files

        使用示例:
            # 周报场景：获取最近 7 天
            commits = fetcher.fetch(..., days=7)

            # 简历场景：获取全部
            commits = fetcher.fetch(...)
        """
        repo = Repo(repo_path)

        # 计算时间范围
        log_kwargs = {}
        if since:
            log_kwargs["since"] = since
        elif days is not None:
            log_kwargs["since"] = datetime.now() - timedelta(days=days)
        # days=None 且 since=None 时，获取全部 commits

        if author:
            log_kwargs["author"] = author

        commits = []
        for commit in repo.iter_commits(branch, **log_kwargs):
            commits.append({
                "hash": commit.hexsha[:7],
                "author": str(commit.author.name),
                "date": commit.committed_datetime,
                "message": commit.message.strip(),
                "files": list(commit.stats.files.keys())
            })

        return commits
