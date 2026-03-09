"""Git工具模块测试"""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from git import Repo
import tempfile
import shutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.git_utils import GitUtils


class TestGitUtils(unittest.TestCase):
    """Git工具测试类"""

    def setUp(self):
        """测试前准备"""
        self.git_utils = GitUtils()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_validate_repo_with_invalid_path(self):
        """测试验证无效仓库"""
        invalid_path = str(Path(self.temp_dir) / "non_existent")
        result = self.git_utils.validate_repo(invalid_path)
        self.assertFalse(result)

    def test_validate_repo_with_non_git_directory(self):
        """测试验证非Git目录"""
        non_git_dir = Path(self.temp_dir) / "not_a_repo"
        non_git_dir.mkdir()
        result = self.git_utils.validate_repo(str(non_git_dir))
        self.assertFalse(result)

    def test_validate_repo_with_valid_repo(self):
        """测试验证有效Git仓库"""
        # 创建一个测试仓库
        repo_dir = Path(self.temp_dir) / "test_repo"
        repo_dir.mkdir()
        Repo.init(repo_dir)

        result = self.git_utils.validate_repo(str(repo_dir))
        self.assertTrue(result)

    def test_get_branches_empty_repo(self):
        """测试获取空仓库的分支"""
        repo_dir = Path(self.temp_dir) / "test_repo"
        repo_dir.mkdir()
        Repo.init(repo_dir)

        branches = self.git_utils.get_branches(str(repo_dir))
        self.assertTrue(len(branches) > 0)
        self.assertTrue("main" in branches or "master" in branches)

    def test_format_commits_for_prompt_empty_list(self):
        """测试格式化空提交列表"""
        result = self.git_utils.format_commits_for_prompt([])
        self.assertEqual(result, "该时间段内没有提交记录。")

    def test_format_commits_for_prompt_with_commits(self):
        """测试格式化提交列表"""
        commits = [
            {
                "hash": "abc123",
                "author": "Test User",
                "date": "2024-01-01 10:00:00",
                "message": "Test commit"
            }
        ]
        result = self.git_utils.format_commits_for_prompt(commits)
        self.assertIn("Test User", result)
        self.assertIn("abc123", result)
        self.assertIn("Test commit", result)


if __name__ == '__main__':
    unittest.main()
