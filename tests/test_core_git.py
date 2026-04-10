"""测试公共 Git 模块"""
import pytest
from datetime import datetime, timedelta
from src.core.git.commit_fetcher import CommitFetcher, CommitInfo
from src.core.git.task_classifier import TaskClassifier, CommitFilter
from src.core.git.commit_splitter import CommitSplitter
from src.core.git.commit_aggregator import CommitAggregator
from src.core.git.repo import GitRepoService, GitContext


class TestCommitFetcher:
    """测试 Commit 获取器"""

    def test_fetch_with_days(self, sample_repo_path):
        """测试获取最近 N 天的 commits"""
        fetcher = CommitFetcher()
        commits = fetcher.fetch(
            repo_path=sample_repo_path,
            branch="main",
            author="test",
            days=7
        )
        assert isinstance(commits, list)
        # 验证返回的是 CommitInfo 对象
        if commits:
            for commit in commits:
                assert isinstance(commit, CommitInfo)
                assert commit.hash
                # 时间可能有 timezone，不做严格比较
                assert commit.date is not None

    def test_fetch_all(self, sample_repo_path):
        """测试获取全部 commits（简历场景）"""
        fetcher = CommitFetcher()
        commits = fetcher.fetch(
            repo_path=sample_repo_path,
            branch="main",
            author="test"
            # 不传 days，获取全部
        )
        assert isinstance(commits, list)


class TestTaskClassifier:
    """测试任务分类器"""

    def test_filter_commits(self):
        """测试过滤 commits"""
        commits = [
            {"hash": "abc123", "message": "Merge branch feature"},
            {"hash": "def456", "message": "test commit"},
            {"hash": "ghi789", "message": "feat: add feature"},
        ]
        filtered, stats = CommitFilter.filter_commits(commits)
        assert len(filtered) == 1
        assert filtered[0]["hash"] == "ghi789"

    def test_classify_commits(self):
        """测试分类 commits"""
        commits = [
            {"hash": "abc123", "message": "feat(api): add user endpoint"},
            {"hash": "def456", "message": "fix: resolve bug"},
        ]
        classified = TaskClassifier.classify_commits(commits)
        assert len(classified) == 2
        assert classified[0]["type"] == "feature"
        assert classified[1]["type"] == "fix"


class TestCommitSplitter:
    """测试 Commit 拆分器"""

    def test_split_markdown_format(self):
        """测试拆分 Markdown 格式"""
        message = """
## 功能模块
1. 添加用户登录
2. 实现权限管理

## 修复
1. 修复登录bug
"""
        result = CommitSplitter.split({"message": message})
        assert len(result) >= 2

    def test_split_dash_list(self):
        """测试拆分 - 列表格式"""
        message = """- 添加用户登录
- 实现权限管理
- 修复登录bug"""
        result = CommitSplitter.split({"message": message})
        assert len(result) >= 2


class TestCommitAggregator:
    """测试 Commit 聚合器"""

    def test_aggregate_by_project(self):
        """测试按项目聚合"""
        commits = [
            {"type": "feature", "scope": "api", "tasks": ["add user", "add login"], "source_commits": ["abc123"]},
            {"type": "fix", "scope": "ui", "tasks": ["fix button"], "source_commits": ["def456"]},
        ]
        aggregated = CommitAggregator.aggregate(commits, "test-project")
        assert len(aggregated) == 2
        assert aggregated[0]["task_count"] == 2


class TestGitRepoService:
    """测试 Git 仓库服务"""

    def test_get_context(self, sample_repo_path):
        """测试获取 Git 上下文"""
        service = GitRepoService()
        context = service.get_context(sample_repo_path, "main")
        assert isinstance(context, GitContext)
        assert context.path == sample_repo_path
        assert context.branch == "main"
        # claude_md 和 readme 可能为 None


@pytest.fixture
def sample_repo_path(tmp_path):
    """创建测试仓库"""
    from git import Repo
    import os

    repo_path = tmp_path / "test_repo"
    repo = Repo.init(repo_path, initial_branch="main")

    # 创建一个测试文件并提交
    test_file = repo_path / "test.txt"
    test_file.write_text("test content")

    # 配置 git
    with repo.config_writer() as config:
        config.set_value("user", "name", "Test User")
        config.set_value("user", "email", "test@example.com")

    # 提交
    repo.index.add(["test.txt"])
    repo.index.commit("feat: add test file")

    return str(repo_path)
