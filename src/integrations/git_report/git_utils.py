"""Git工具模块"""
import os
from datetime import datetime
from typing import List, Dict, Optional
from git import Repo, GitCommandError, InvalidGitRepositoryError


class GitUtils:
    """Git工具类"""

    @staticmethod
    def get_branches(repo_path: str) -> List[str]:
        """
        获取仓库的所有分支

        Args:
            repo_path: Git仓库路径

        Returns:
            分支名称列表

        Raises:
            InvalidGitRepositoryError: 无效的Git仓库
        """
        try:
            repo = Repo(repo_path)
            # 获取本地分支
            branches = [head.name for head in repo.heads]
            return sorted(branches)
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(f"不是有效的Git仓库: {repo_path}")

    @staticmethod
    def get_commits(
        repo_path: str,
        branch: str = "main",
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        author: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        获取指定时间范围内的提交记录

        Args:
            repo_path: Git仓库路径
            branch: 分支名称
            since: 起始时间
            until: 结束时间
            author: 作者筛选（可选）

        Returns:
            提交记录列表，每个记录包含hash、作者、日期、消息
        """
        try:
            repo = Repo(repo_path)

            # 构建日志参数
            log_kwargs = {}
            if since:
                log_kwargs["since"] = since
            if until:
                log_kwargs["until"] = until
            if author:
                log_kwargs["author"] = author

            # 获取提交记录
            commits = []
            for commit in repo.iter_commits(branch, **log_kwargs):
                commits.append(
                    {
                        "hash": commit.hexsha[:7],
                        "author": str(commit.author),
                        "date": commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                        "message": commit.message.strip(),
                    }
                )

            return commits

        except GitCommandError as e:
            raise RuntimeError(f"Git命令执行失败: {e}")
        except InvalidGitRepositoryError:
            raise InvalidGitRepositoryError(f"不是有效的Git仓库: {repo_path}")

    @staticmethod
    def validate_repo(repo_path: str) -> bool:
        """
        验证是否是有效的Git仓库

        Args:
            repo_path: Git仓库路径

        Returns:
            是否有效
        """
        try:
            Repo(repo_path)
            return True
        except Exception:
            return False

    @staticmethod
    def format_commits_for_prompt(commits: List[Dict[str, str]]) -> str:
        """
        将提交记录格式化为提示词文本

        Args:
            commits: 提交记录列表

        Returns:
            格式化后的文本
        """
        if not commits:
            return "该时间段内没有提交记录。"

        lines = []
        for commit in commits:
            lines.append(
                f"[{commit['date']}] {commit['author']} - {commit['hash']}\n"
                f"  {commit['message']}\n"
            )

        return "\n".join(lines)
