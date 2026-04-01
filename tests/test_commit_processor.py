"""Commit 处理模块测试 - V0.3"""
import unittest
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.commit_processor import (
    CommitFilterV02,
    CommitClassifierV02,
    CommitSplitterV03,
    CommitType,
    process_commits
)


class TestCommitFilterV02(unittest.TestCase):
    """Commit 过滤器测试"""

    def test_filter_merge_branch(self):
        """测试过滤 Merge branch"""
        message = "Merge branch 'feature' into main"
        should_filter, reason = CommitFilterV02.should_filter(message)
        self.assertTrue(should_filter)
        self.assertEqual(reason, "Merge branch")

    def test_filter_test_commits(self):
        """测试过滤包含 test 的 commit"""
        message = "fix: test login issue"
        should_filter, reason = CommitFilterV02.should_filter(message)
        self.assertTrue(should_filter)
        self.assertEqual(reason, "包含test")

    def test_filter_short_messages(self):
        """测试过滤短消息"""
        should_filter, reason = CommitFilterV02.should_filter("abc")
        self.assertTrue(should_filter)
        should_filter, reason = CommitFilterV02.should_filter("fix")
        self.assertTrue(should_filter)
        should_filter, reason = CommitFilterV02.should_filter("")
        self.assertTrue(should_filter)


    def test_keep_valid_commits(self):
        """测试保留有效 commit"""
        should_filter, reason = CommitFilterV02.should_filter("feat: 添加用户登录功能")
        self.assertFalse(should_filter)
        should_filter, reason = CommitFilterV02.should_filter("修复登录问题")
        self.assertFalse(should_filter)
        should_filter, reason = CommitFilterV02.should_filter("新加坡xxx改动合并德国")
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
        filtered, filter_stats = CommitFilterV02.filter_commits(commits)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["hash"], "004")
        self.assertEqual(filtered[1]["hash"], "005")
        # 验证过滤统计
        self.assertEqual(filter_stats.get("Merge branch"), 1)
        self.assertEqual(filter_stats.get("包含test"), 1)
        self.assertEqual(filter_stats.get("长度<5"), 1)


class TestCommitClassifierV02(unittest.TestCase):
    """Commit 分类器测试"""

    def test_parse_standard_format_with_scope(self):
        """测试解析标准格式（带 scope）"""
        message = "fix(perms): 修复权限问题"
        result = CommitClassifierV02._parse_standard_format(message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "fix")
        self.assertEqual(result[1], "perms")
        self.assertEqual(result[2], "修复权限问题")

    def test_parse_standard_format_without_scope(self):
        """测试解析简化格式"""
        message = "fix: 修复权限问题"
        result = CommitClassifierV02._parse_standard_format(message)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "fix")
        self.assertEqual(result[1], "default")
        self.assertEqual(result[2], "修复权限问题")

    def test_parse_non_standard_format(self):
        """测试解析非标准格式"""
        message = "新加坡xxx改动合并德国"
        result = CommitClassifierV02._parse_standard_format(message)
        self.assertIsNone(result)

    def test_parse_standard_format_multiline(self):
        """测试解析多行标准格式"""
        message = """feat(perms): 新增商户角色时自动添加默认菜单权限

- 新增 getDefaultMenuCodes() 方法
- 新增 setDefaultMenusForRole() 方法

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"""
        result = CommitClassifierV02._parse_standard_format(message)
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
                result = CommitClassifierV02._classify_by_keywords(message)
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
                result = CommitClassifierV02._classify_by_keywords(message)
                self.assertEqual(result, expected_type)

    def test_classify_default_refactor(self):
        """测试默认 refactor 分类"""
        message = "优化代码结构"
        result = CommitClassifierV02._classify_by_keywords(message)
        self.assertEqual(result, CommitType.REFACTOR.value)

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
                result = CommitClassifierV02._normalize_type(input_type)
                self.assertEqual(result, expected)

    def test_classify_standard_format(self):
        """测试分类标准格式 commit"""
        commit = {
            "hash": "abc123",
            "message": "fix(perms): 修复权限问题"
        }
        result = CommitClassifierV02.classify(commit)
        self.assertEqual(result.type, CommitType.FIX.value)
        self.assertEqual(result.scope, "perms")
        self.assertEqual(result.tasks, ["修复权限问题"])
        self.assertEqual(result.source_commit, "abc123")

    def test_classify_non_standard_format_feat(self):
        """测试分类非标准格式 commit（feat）"""
        commit = {
            "hash": "def456",
            "message": "新加坡xxx改动合并德国"
        }
        result = CommitClassifierV02.classify(commit)
        self.assertEqual(result.type, CommitType.FEAT.value)
        self.assertEqual(result.scope, "default")
        self.assertEqual(result.tasks, ["新加坡xxx改动合并德国"])

    def test_classify_non_standard_format_fix(self):
        """测试分类非标准格式 commit（fix）"""
        commit = {
            "hash": "ghi789",
            "message": "修复登录问题"
        }
        result = CommitClassifierV02.classify(commit)
        self.assertEqual(result.type, CommitType.FIX.value)
        self.assertEqual(result.scope, "default")
        self.assertEqual(result.tasks, ["修复登录问题"])

    def test_classify_commits_list(self):
        """测试分类 commit 列表"""
        commits = [
            {"hash": "001", "message": "feat: 添加新功能"},
            {"hash": "002", "message": "修复登录问题"},
            {"hash": "003", "message": "新加坡改动上线"},
        ]
        results = CommitClassifierV02.classify_commits(commits)
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
            self.assertIn("tasks", result)
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
            tasks=["添加登录功能"],
            source_commit="abc123"
        )

        result = commit.to_dict()
        self.assertEqual(result["type"], "feature")
        self.assertEqual(result["scope"], "auth")
        self.assertEqual(result["tasks"], ["添加登录功能"])
        self.assertEqual(result["source_commit"], "abc123")


class TestCommitSplitterV03(unittest.TestCase):
    """Commit 拆分器测试 - V0.3"""

    def test_split_markdown_format(self):
        """测试 Markdown 格式拆分"""
        message = """## 功能改进
1. 修复菜单权限问题
2. 优化权限逻辑

## 性能优化
1. 减少数据库查询
2. 添加缓存机制"""
        result = CommitSplitterV03._split_markdown(message)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 1)
        self.assertIn("修复菜单权限问题", result)
        self.assertIn("优化权限逻辑", result)

    def test_split_markdown_no_match(self):
        """测试非 Markdown 格式返回 None"""
        message = "修复登录问题，优化缓存"
        result = CommitSplitterV03._split_markdown(message)
        self.assertIsNone(result)

    def test_split_dash_list(self):
        """测试 - 列表拆分"""
        message = """- 修复菜单权限问题
- 优化权限逻辑
- 添加缓存机制"""
        result = CommitSplitterV03._split_dash_list(message)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "修复菜单权限问题")
        self.assertEqual(result[1], "优化权限逻辑")
        self.assertEqual(result[2], "添加缓存机制")

    def test_split_dash_list_without_space(self):
        """测试 - 列表拆分（无空格）"""
        message = """-修复菜单权限问题
-优化权限逻辑"""
        result = CommitSplitterV03._split_dash_list(message)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)

    def test_split_dash_list_no_match(self):
        """测试非列表格式返回 None"""
        message = "修复登录问题，优化缓存"
        result = CommitSplitterV03._split_dash_list(message)
        self.assertIsNone(result)

    def test_split_by_separators_chinese_comma(self):
        """测试中文逗号分隔符拆分"""
        message = "修复登录问题，优化缓存，添加测试"
        result = CommitSplitterV03._split_by_separators(message)
        self.assertGreater(len(result), 1)
        self.assertIn("修复登录问题", result)
        self.assertIn("优化缓存", result)
        self.assertIn("添加测试", result)

    def test_split_by_separators_english_comma(self):
        """测试英文逗号分隔符拆分"""
        message = "fix login, optimize cache, add tests"
        result = CommitSplitterV03._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_and(self):
        """测试 and 分隔符拆分"""
        message = "fix login and optimize cache and add tests"
        result = CommitSplitterV03._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_plus(self):
        """测试 + 分隔符拆分"""
        message = "修复登录 + 优化缓存 + 添加测试"
        result = CommitSplitterV03._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_yiji(self):
        """测试 以及 分隔符拆分"""
        message = "修复登录以及优化缓存以及添加测试"
        result = CommitSplitterV03._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_single_item(self):
        """测试单行文本返回原值"""
        message = "修复登录问题"
        result = CommitSplitterV03._split_by_separators(message)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "修复登录问题")

    def test_count_sentences(self):
        """测试句子数量统计"""
        self.assertEqual(CommitSplitterV03._count_sentences("一个句子"), 1)
        self.assertEqual(CommitSplitterV03._count_sentences("两个句子。这是第二个"), 2)
        self.assertEqual(CommitSplitterV03._count_sentences("Three sentences. And another one! Last one?"), 3)

    def test_split_short_text_no_llm(self):
        """测试短文本不进行 LLM 拆分"""
        classified = {
            'type': 'fix',
            'scope': 'default',
            'message': '修复登录问题',
            'source_commit': 'abc123'
        }
        result = CommitSplitterV03.split(classified, llm_client=None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], '修复登录问题')

    def test_split_long_text_no_llm(self):
        """测试长文本无 LLM 时保持原文"""
        classified = {
            'type': 'fix',
            'scope': 'default',
            'message': '这是一个比较长的提交消息描述了一个复杂的功能实现包含了多个子任务的完成情况',  # 无分隔符
            'source_commit': 'abc123'
        }
        result = CommitSplitterV03.split(classified, llm_client=None)
        # 无 LLM 客户端且无分隔符时，长文本保持原文作为单一任务
        self.assertEqual(len(result), 1)

    def test_split_commits_list(self):
        """测试拆分 commit 列表"""
        classified_commits = [
            {
                'type': 'fix',
                'scope': 'perms',
                'message': '- 修复菜单权限问题\n- 优化权限逻辑',
                'source_commit': 'abc123'
            },
            {
                'type': 'feat',
                'scope': 'default',
                'message': '修复登录问题，优化缓存',
                'source_commit': 'def456'
            }
        ]
        results = CommitSplitterV03.split_commits(classified_commits, llm_client=None)

        self.assertEqual(len(results), 2)
        # 第一个应该被拆分为 2 个任务
        self.assertEqual(len(results[0]['tasks']), 2)
        # 第二个应该被拆分为 2 个任务
        self.assertEqual(len(results[1]['tasks']), 2)

        # 验证数据结构
        self.assertIn('type', results[0])
        self.assertIn('scope', results[0])
        self.assertIn('tasks', results[0])
        self.assertIn('source_commit', results[0])
        self.assertNotIn('message', results[0])


class TestProcessCommitsV03(unittest.TestCase):
    """完整处理流程测试 - V0.3"""

    def test_process_commits_with_split(self):
        """测试完整流程：过滤 -> 分类 -> 拆分"""
        commits = [
            # 应该被过滤
            {"hash": "001", "message": "Merge branch 'feature'"},
            {"hash": "002", "message": "test: 单元测试"},
            # 应该保留并拆分
            {"hash": "003", "message": "feat: 添加用户登录，优化权限，修复缓存"},
            {"hash": "004", "message": "- 修复菜单权限问题\n- 优化权限逻辑"},
        ]

        results = process_commits(commits, llm_client=None)

        # 应该保留 2 个
        self.assertEqual(len(results), 2)

        # 验证数据结构包含 tasks
        self.assertIn('tasks', results[0])
        self.assertIn('tasks', results[1])

        # 第一个应该被分隔符拆分
        self.assertGreater(len(results[0]['tasks']), 1)

        # 第二个应该被列表拆分
        self.assertEqual(len(results[1]['tasks']), 2)

    def test_process_result_structure(self):
        """测试结果数据结构"""
        commits = [
            {"hash": "001", "message": "fix: 修复登录问题"}
        ]

        results = process_commits(commits, llm_client=None)

        self.assertEqual(len(results), 1)
        result = results[0]

        # 验证必需字段
        self.assertIn('type', result)
        self.assertIn('scope', result)
        self.assertIn('tasks', result)
        self.assertIn('source_commit', result)

        # 验证 tasks 是列表
        self.assertIsInstance(result['tasks'], list)


if __name__ == '__main__':
    unittest.main()
