"""Commit 处理模块测试 - V0.2"""
import unittest
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.commit_processor import (
    CommitFilter,
    CommitClassifier,
    CommitType,
    process_commits
)


class TestCommitFilter(unittest.TestCase):
    """Commit 过滤器测试"""

    def test_filter_merge_branch(self):
        """测试过滤 Merge branch"""
        message = "Merge branch 'feature' into main"
        should_filter, reason = CommitFilter.should_filter(message)
        self.assertTrue(should_filter)
        self.assertEqual(reason, "Merge branch")

    def test_filter_test_commits(self):
        """测试过滤包含 test 的 commit"""
        message = "fix: test login issue"
        should_filter, reason = CommitFilter.should_filter(message)
        self.assertTrue(should_filter)
        self.assertEqual(reason, "包含test")

    def test_filter_short_messages(self):
        """测试过滤短消息"""
        should_filter, reason = CommitFilter.should_filter("abc")
        self.assertTrue(should_filter)
        should_filter, reason = CommitFilter.should_filter("fix")
        self.assertTrue(should_filter)
        should_filter, reason = CommitFilter.should_filter("")
        self.assertTrue(should_filter)


    def test_keep_valid_commits(self):
        """测试保留有效 commit"""
        should_filter, reason = CommitFilter.should_filter("feat: 添加用户登录功能")
        self.assertFalse(should_filter)
        should_filter, reason = CommitFilter.should_filter("修复登录问题")
        self.assertFalse(should_filter)
        should_filter, reason = CommitFilter.should_filter("新加坡xxx改动合并德国")
        self.assertFalse(should_filter)

    def test_filter_commits_list(self):
        """测试过滤 commit 列表"""
        commits = [
            {"hash": "001", "message": "Merge branch 'feature'"},
            {"hash": "002", "message": "fix: test bug"},
            {"hash": "003", "message": "abc"},
            {"hash": "004", "message": "feat: 添加新功能"},
            {"hash": "005", "message": "修复登录问题"},
        ]
        filtered = CommitFilter.filter_commits(commits)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["hash"], "004")
        self.assertEqual(filtered[1]["hash"], "005")


class TestCommitClassifier(unittest.TestCase):
    """Commit 分类器测试"""

    def test_parse_standard_format_with_scope(self):
        """测试解析标准格式（带 scope）"""
        message = "fix(perms): 修复权限问题"
        result = CommitClassifier._parse_standard_format(message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "fix")
        self.assertEqual(result[1], "perms")
        self.assertEqual(result[2], "修复权限问题")

    def test_parse_standard_format_without_scope(self):
        """测试解析简化格式"""
        message = "fix: 修复权限问题"
        result = CommitClassifier._parse_standard_format(message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "fix")
        self.assertEqual(result[1], "default")
        self.assertEqual(result[2], "修复权限问题")

    def test_parse_non_standard_format(self):
        """测试解析非标准格式"""
        message = "新加坡xxx改动合并德国"
        result = CommitClassifier._parse_standard_format(message)
        self.assertIsNone(result)

    def test_parse_standard_format_multiline(self):
        """测试解析多行标准格式"""
        message = """feat(perms): 新增商户角色时自动添加默认菜单权限

- 新增 getDefaultMenuCodes() 方法
- 新增 setDefaultMenusForRole() 方法

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"""
        result = CommitClassifier._parse_standard_format(message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "feat")
        self.assertEqual(result[1], "perms")
        self.assertIn("新增商户角色时自动添加默认菜单权限", result[2])

    def test_classify_feat_keywords(self):
        """测试 feat 关键词分类"""
        test_cases = [
            ("新加坡xxx改动合并德国", CommitType.FEAT.value),
            ("发布新版本", CommitType.FEAT.value),
            ("上线生产环境", CommitType.FEAT.value),
            ("巴西环境配置", CommitType.FEAT.value),
        ]
        for message, expected_type in test_cases:
            with self.subTest(message=message):
                result = CommitClassifier._classify_by_keywords(message)
                self.assertEqual(result, expected_type)

    def test_classify_fix_keywords(self):
        """测试 fix 关键词分类"""
        test_cases = [
            ("修复登录问题", CommitType.FIX.value),
            ("fix menu bug", CommitType.FIX.value),
            ("处理线上问题", CommitType.FIX.value),
        ]
        for message, expected_type in test_cases:
            with self.subTest(message=message):
                result = CommitClassifier._classify_by_keywords(message)
                self.assertEqual(result, expected_type)

    def test_classify_default_refactor(self):
        """测试默认 refactor 分类"""
        message = "优化代码结构"
        result = CommitClassifier._classify_by_keywords(message)
        self.assertEqual(result, CommitType.REFACTOR.value)

    def test_extract_scope_with_parentheses(self):
        """测试提取有括号的 scope"""
        message = "feat(perms): 添加权限功能"
        result = CommitClassifier._extract_scope(message)
        self.assertEqual(result, "perms")

    def test_extract_scope_without_parentheses(self):
        """测试提取无括号的 scope"""
        message = "添加权限功能"
        result = CommitClassifier._extract_scope(message)
        self.assertEqual(result, "default")

    def test_normalize_type(self):
        """测试 type 标准化"""
        test_cases = [
            ("feat", CommitType.FEAT.value),
            ("feature", CommitType.FEAT.value),
            ("fix", CommitType.FIX.value),
            ("refactor", CommitType.REFACTOR.value),
            ("unknown", CommitType.REFACTOR.value),
        ]
        for input_type, expected in test_cases:
            with self.subTest(type=input_type):
                result = CommitClassifier._normalize_type(input_type)
                self.assertEqual(result, expected)

    def test_classify_standard_format(self):
        """测试分类标准格式 commit"""
        commit = {
            "hash": "abc123",
            "message": "fix(perms): 修复权限问题"
        }
        result = CommitClassifier.classify(commit)
        self.assertEqual(result.type, CommitType.FIX.value)
        self.assertEqual(result.scope, "perms")
        self.assertEqual(result.message, "修复权限问题")
        self.assertEqual(result.source_commit, "abc123")

    def test_classify_non_standard_format_feat(self):
        """测试分类非标准格式 commit（feat）"""
        commit = {
            "hash": "def456",
            "message": "新加坡xxx改动合并德国"
        }
        result = CommitClassifier.classify(commit)
        self.assertEqual(result.type, CommitType.FEAT.value)
        self.assertEqual(result.scope, "default")
        self.assertEqual(result.message, "新加坡xxx改动合并德国")

    def test_classify_non_standard_format_fix(self):
        """测试分类非标准格式 commit（fix）"""
        commit = {
            "hash": "ghi789",
            "message": "修复登录问题"
        }
        result = CommitClassifier.classify(commit)
        self.assertEqual(result.type, CommitType.FIX.value)
        self.assertEqual(result.scope, "default")

    def test_classify_commits_list(self):
        """测试分类 commit 列表"""
        commits = [
            {"hash": "001", "message": "feat: 添加新功能"},
            {"hash": "002", "message": "修复登录问题"},
            {"hash": "003", "message": "新加坡改动上线"},
        ]
        results = CommitClassifier.classify_commits(commits)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["type"], CommitType.FEAT.value)
        self.assertEqual(results[1]["type"], CommitType.FIX.value)
        self.assertEqual(results[2]["type"], CommitType.FEAT.value)


class TestProcessCommits(unittest.TestCase):
    """完整处理流程测试"""

    def test_process_commits_full_workflow(self):
        """测试完整处理流程：过滤 -> 分类"""
        commits = [
            # 应该被过滤
            {"hash": "001", "message": "Merge branch 'feature'"},
            {"hash": "002", "message": "test: 单元测试"},
            {"hash": "003", "message": "fix"},
            # 应该保留
            {"hash": "004", "message": "feat: 添加用户登录"},
            {"hash": "005", "message": "修复登录问题"},
            {"hash": "006", "message": "新加坡xxx改动合并德国"},
        ]

        results = process_commits(commits)

        # 应该只保留 3 个
        self.assertEqual(len(results), 3)

        # 验证分类结果
        self.assertEqual(results[0]["type"], CommitType.FEAT.value)
        self.assertEqual(results[1]["type"], CommitType.FIX.value)
        self.assertEqual(results[2]["type"], CommitType.FEAT.value)

        # 验证数据结构
        for result in results:
            self.assertIn("type", result)
            self.assertIn("scope", result)
            self.assertIn("message", result)
            self.assertIn("source_commit", result)

    def test_process_empty_commits(self):
        """测试处理空列表"""
        results = process_commits([])
        self.assertEqual(len(results), 0)

    def test_process_all_filtered_commits(self):
        """测试所有 commit 都被过滤"""
        commits = [
            {"hash": "001", "message": "Merge branch"},
            {"hash": "002", "message": "test"},
            {"hash": "003", "message": "fix"},
        ]
        results = process_commits(commits)
        self.assertEqual(len(results), 0)


class TestDataStructure(unittest.TestCase):
    """数据结构测试"""

    def test_classified_commit_to_dict(self):
        """测试 ClassifiedCommit 转换为字典"""
        from src.commit_processor import ClassifiedCommit

        commit = ClassifiedCommit(
            type="feature",
            scope="auth",
            message="添加登录功能",
            source_commit="abc123"
        )

        result = commit.to_dict()
        self.assertEqual(result["type"], "feature")
        self.assertEqual(result["scope"], "auth")
        self.assertEqual(result["message"], "添加登录功能")
        self.assertEqual(result["source_commit"], "abc123")


if __name__ == '__main__':
    unittest.main()
