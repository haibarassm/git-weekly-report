"""ReportApp 模块测试 - V0.2 补充"""
import unittest
import tempfile
import shutil
from pathlib import Path
from git import Repo
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import ReportApp


class TestReportAppGetBranches(unittest.TestCase):
    """ReportApp.get_branches 边界测试 - V0.2"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        # 创建一个临时 base_dir
        self.base_dir = Path(self.temp_dir)
        self.app = ReportApp()
        # 覆盖 base_dir
        self.app.base_dir = self.base_dir

    def tearDown(self):
        """测试后清理"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_get_branches_with_empty_project_name(self):
        """测试空项目名返回空列表"""
        branches = self.app.get_branches("")
        self.assertEqual(branches, [])

    def test_get_branches_with_none_project_name(self):
        """测试 None 项目名返回空列表"""
        branches = self.app.get_branches(None)
        self.assertEqual(branches, [])

    def test_get_branches_with_non_existent_project(self):
        """测试不存在的项目路径返回空列表"""
        branches = self.app.get_branches("non_existent_project")
        self.assertEqual(branches, [])

    def test_get_branches_with_non_git_directory(self):
        """测试非 Git 目录返回空列表"""
        # 创建一个普通目录
        non_git_dir = self.base_dir / "not_a_repo"
        non_git_dir.mkdir()

        branches = self.app.get_branches("not_a_repo")
        self.assertEqual(branches, [])

    def test_get_branches_with_valid_git_repo(self):
        """测试有效的 Git 仓库返回分支列表"""
        # 创建一个测试仓库
        repo_dir = self.base_dir / "test_repo"
        repo_dir.mkdir()
        repo = Repo.init(repo_dir)

        # 配置 Git 用户信息
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")

        # 创建一个提交以生成分支
        test_file = repo_dir / "test.txt"
        test_file.write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        repo.close()

        branches = self.app.get_branches("test_repo")

        # 应该返回非空列表
        self.assertIsInstance(branches, list)
        self.assertGreater(len(branches), 0)
        # 应该包含 main 或 master
        self.assertTrue("main" in branches or "master" in branches)

    def test_get_branches_handles_exception_gracefully(self):
        """测试 get_branches 异常处理"""
        # 使用一个会触发异常的路径
        branches = self.app.get_branches("../invalid/path/../../overly/nested/path")
        self.assertEqual(branches, [])


class TestReportAppGetProjects(unittest.TestCase):
    """ReportApp.get_projects 边界测试 - V0.2"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.base_dir = Path(self.temp_dir)

    def tearDown(self):
        """测试后清理"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_get_projects_with_non_existent_base_dir(self):
        """测试不存在的 base_dir 返回空列表"""
        app = ReportApp()
        app.base_dir = Path(self.temp_dir) / "non_existent"

        projects = app.get_projects()
        self.assertEqual(projects, [])

    def test_get_projects_with_empty_base_dir(self):
        """测试空的 base_dir 返回空列表"""
        app = ReportApp()
        app.base_dir = self.base_dir

        projects = app.get_projects()
        self.assertEqual(projects, [])

    def test_get_projects_with_git_repos(self):
        """测试包含 Git 仓库的 base_dir 返回项目列表"""
        # 创建几个测试仓库
        for repo_name in ["project1", "project2"]:
            repo_dir = self.base_dir / repo_name
            repo_dir.mkdir()
            repo = Repo.init(repo_dir)

            with repo.config_writer() as config:
                config.set_value("user", "name", "Test User")
                config.set_value("user", "email", "test@example.com")

            test_file = repo_dir / "test.txt"
            test_file.write_text("test")
            repo.index.add(["test.txt"])
            repo.index.commit("Initial commit")
            repo.close()

        app = ReportApp()
        app.base_dir = self.base_dir

        projects = app.get_projects()

        self.assertEqual(len(projects), 2)
        self.assertIn("project1", projects)
        self.assertIn("project2", projects)


if __name__ == '__main__':
    unittest.main()
