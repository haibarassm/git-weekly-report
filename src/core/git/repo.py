"""Git 仓库操作 - 读取 claude.md、README、获取分支等"""
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class GitContext:
    """Git 上下文"""
    path: str
    branch: str
    claude_md: Optional[str] = None
    readme: Optional[str] = None


class GitRepoService:
    """Git 仓库服务 - 读取项目文档、获取分支等"""

    @staticmethod
    def get_context(path: str, branch: str) -> GitContext:
        """获取项目的 Git 上下文（claude.md, readme）

        Args:
            path: 仓库路径
            branch: 分支名

        Returns:
            GitContext
        """
        claude_md = GitRepoService._read_claude_md(path)
        readme = GitRepoService._read_readme(path)
        return GitContext(path=path, branch=branch, claude_md=claude_md, readme=readme)

    @staticmethod
    def get_branches(repo_path: str) -> List[str]:
        """
        获取仓库的所有分支

        Args:
            repo_path: Git仓库路径

        Returns:
            分支名称列表
        """
        from git import Repo
        try:
            repo = Repo(repo_path)
            branches = set()

            # 获取本地分支
            for head in repo.heads:
                branches.add(head.name)

            # 获取远程分支（去掉 origin/ 前缀）
            for ref in repo.remote().refs:
                full_name = ref.name
                branch_name = full_name.replace('origin/', '', 1)

                # 去掉 refs/heads/、refs/tags/ 等前缀
                if branch_name.startswith('refs/heads/'):
                    branch_name = branch_name.replace('refs/heads/', '', 1)
                elif branch_name.startswith('refs/tags/'):
                    branch_name = branch_name.replace('refs/tags/', '', 1)

                branches.add(branch_name)

            # 如果当前处于 detached HEAD 状态，添加当前 HEAD 引用
            if repo.head.is_detached:
                try:
                    current_commit = repo.head.commit.hexsha[:7]
                    branches.add(f"HEAD@{{{current_commit}}}")
                except:
                    pass

            return sorted(list(branches))
        except Exception as e:
            import logging
            logging.warning(f"获取分支失败 {repo_path}: {e}")
            return ["main", "master"]

    @staticmethod
    def validate_repo(repo_path: str) -> bool:
        """
        验证是否是有效的Git仓库

        Args:
            repo_path: Git仓库路径

        Returns:
            是否有效
        """
        from git import Repo
        try:
            Repo(repo_path)
            return True
        except Exception:
            return False

    @staticmethod
    def _read_claude_md(path: str) -> Optional[str]:
        """读取 .claude/CLAUDE.md"""
        claude_path = Path(path) / ".claude" / "CLAUDE.md"
        if claude_path.exists():
            return claude_path.read_text(encoding='utf-8')
        return None

    @staticmethod
    def _read_readme(path: str) -> Optional[str]:
        """读取 README（优先级：README.md > readme.md > README）"""
        for name in ["README.md", "readme.md", "README"]:
            readme_path = Path(path) / name
            if readme_path.exists():
                return readme_path.read_text(encoding='utf-8')
        return None
