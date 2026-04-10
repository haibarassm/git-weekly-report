"""Git 仓库操作 - 读取 claude.md 和 README"""
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class GitContext:
    """Git 上下文"""
    path: str
    branch: str
    claude_md: Optional[str] = None
    readme: Optional[str] = None


class GitRepoService:
    """Git 仓库服务 - 读取项目文档"""

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
