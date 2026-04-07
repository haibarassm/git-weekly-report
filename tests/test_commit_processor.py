"""Commit 处理模块测试"""
import unittest
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.commit_processor import (
    CommitFilter,
    CommitClassifier,
    CommitSplitter,
    TaskAggregator,
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
        filtered, filter_stats = CommitFilter.filter_commits(commits)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0]["hash"], "004")
        self.assertEqual(filtered[1]["hash"], "005")
        # 验证过滤统计
        self.assertEqual(filter_stats.get("Merge branch"), 1)
        self.assertEqual(filter_stats.get("包含test"), 1)
        self.assertEqual(filter_stats.get("长度<5"), 1)


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
        self.assertEqual(result.tasks, ["修复权限问题"])
        self.assertEqual(result.source_commit, "abc123")

    def test_classify_non_standard_format_feat(self):
        """测试分类非标准格式 commit（feat）"""
        commit = {
            "hash": "def456",
            "message": "新加坡xxx改动合并德国"
        }
        result = CommitClassifier.classify(commit)
        self.assertEqual(result.type, CommitType.FEAT.value)
        # 包含"新加坡"，应该被识别为 release scope
        self.assertEqual(result.scope, "release")
        self.assertEqual(result.tasks, ["新加坡xxx改动合并德国"])

    def test_classify_non_standard_format_fix(self):
        """测试分类非标准格式 commit（fix）"""
        commit = {
            "hash": "ghi789",
            "message": "修复登录问题"
        }
        result = CommitClassifier.classify(commit)
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
        results = CommitClassifier.classify_commits(commits)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["type"], CommitType.FEAT.value)
        self.assertEqual(results[1]["type"], CommitType.FIX.value)
        self.assertEqual(results[2]["type"], CommitType.FEAT.value)
        # 第三个应该是 release scope
        self.assertEqual(results[2]["scope"], "release")

    def test_classify_release_scope(self):
        """测试发布相关 commit 的特殊 scope"""
        test_cases = [
            ("发布到新加坡环境", "release"),
            ("德国环境上线", "release"),
            ("巴西版本发布", "release"),
            ("fix(release): 修复线上问题", "release"),  # 标准格式但保留 release
        ]
        for message, expected_scope in test_cases:
            with self.subTest(message=message):
                commit = {"hash": "abc", "message": message}
                result = CommitClassifier.classify(commit)
                self.assertEqual(result.scope, expected_scope)


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

        # 禁用 V0.4 以保持原有测试行为
        results = process_commits(commits, enable_v04=False)

        # 应该只保留 3 个
        self.assertEqual(len(results), 3)

        # 验证分类结果
        self.assertEqual(results[0]["type"], CommitType.FEAT.value)
        self.assertEqual(results[1]["type"], CommitType.FIX.value)
        self.assertEqual(results[2]["type"], CommitType.FEAT.value)

        # 验证数据结构（V0.3 格式）
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


class TestCommitSplitter(unittest.TestCase):
    """Commit 拆分器测试 - V0.3"""

    def test_split_markdown_format(self):
        """测试 Markdown 格式拆分"""
        message = """## 功能改进
1. 修复菜单权限问题
2. 优化权限逻辑

## 性能优化
1. 减少数据库查询
2. 添加缓存机制"""
        result = CommitSplitter._split_markdown(message)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 1)
        self.assertIn("修复菜单权限问题", result)
        self.assertIn("优化权限逻辑", result)

    def test_split_markdown_no_match(self):
        """测试非 Markdown 格式返回 None"""
        message = "修复登录问题，优化缓存"
        result = CommitSplitter._split_markdown(message)
        self.assertIsNone(result)

    def test_split_dash_list(self):
        """测试 - 列表拆分"""
        message = """- 修复菜单权限问题
- 优化权限逻辑
- 添加缓存机制"""
        result = CommitSplitter._split_dash_list(message)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "修复菜单权限问题")
        self.assertEqual(result[1], "优化权限逻辑")
        self.assertEqual(result[2], "添加缓存机制")

    def test_split_dash_list_without_space(self):
        """测试 - 列表拆分（无空格）"""
        message = """-修复菜单权限问题
-优化权限逻辑"""
        result = CommitSplitter._split_dash_list(message)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 2)

    def test_split_dash_list_no_match(self):
        """测试非列表格式返回 None"""
        message = "修复登录问题，优化缓存"
        result = CommitSplitter._split_dash_list(message)
        self.assertIsNone(result)

    def test_split_by_separators_chinese_comma(self):
        """测试中文逗号分隔符拆分"""
        message = "修复登录问题，优化缓存，添加测试"
        result = CommitSplitter._split_by_separators(message)
        self.assertGreater(len(result), 1)
        self.assertIn("修复登录问题", result)
        self.assertIn("优化缓存", result)
        self.assertIn("添加测试", result)

    def test_split_by_separators_english_comma(self):
        """测试英文逗号分隔符拆分"""
        message = "fix login, optimize cache, add tests"
        result = CommitSplitter._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_and(self):
        """测试 and 分隔符拆分"""
        message = "fix login and optimize cache and add tests"
        result = CommitSplitter._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_plus(self):
        """测试 + 分隔符拆分"""
        message = "修复登录 + 优化缓存 + 添加测试"
        result = CommitSplitter._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_yiji(self):
        """测试 以及 分隔符拆分"""
        message = "修复登录以及优化缓存以及添加测试"
        result = CommitSplitter._split_by_separators(message)
        self.assertGreater(len(result), 1)

    def test_split_by_separators_single_item(self):
        """测试单行文本返回原值"""
        message = "修复登录问题"
        result = CommitSplitter._split_by_separators(message)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], "修复登录问题")

    def test_count_sentences(self):
        """测试句子数量统计"""
        self.assertEqual(CommitSplitter._count_sentences("一个句子"), 1)
        self.assertEqual(CommitSplitter._count_sentences("两个句子。这是第二个"), 2)
        self.assertEqual(CommitSplitter._count_sentences("Three sentences. And another one! Last one?"), 3)

    def test_split_short_text_no_llm(self):
        """测试短文本不进行 LLM 拆分"""
        classified = {
            'type': 'fix',
            'scope': 'default',
            'message': '修复登录问题',
            'source_commit': 'abc123'
        }
        result = CommitSplitter.split(classified, llm_client=None)
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
        result = CommitSplitter.split(classified, llm_client=None)
        # 无 LLM 客户端且无分隔符时，长文本保持原文作为单一任务
        self.assertEqual(len(result), 1)

    def test_clean_task_removes_coauthor(self):
        """测试清理 Co-Authored-By 签名"""
        task = "修复登录问题\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
        result = CommitSplitter._clean_task(task)
        self.assertEqual(result, "修复登录问题")

    def test_clean_task_removes_leading_junk(self):
        """测试清理开头的无效字符"""
        task1 = "'')确保一级菜单不传parent_code时"
        result1 = CommitSplitter._clean_task(task1)
        self.assertEqual(result1, "确保一级菜单不传parent_code时")

        task2 = "('修复权限问题"
        result2 = CommitSplitter._clean_task(task2)
        self.assertEqual(result2, "修复权限问题")

    def test_clean_task_filters_short(self):
        """测试过滤过短的任务"""
        task = "a"
        result = CommitSplitter._clean_task(task)
        self.assertIsNone(result)

    def test_dedupe_tasks(self):
        """测试任务去重"""
        tasks = [
            "修复菜单权限",
            "优化权限逻辑",
            "修复菜单权限",  # 重复
            "添加缓存",
        ]
        result = CommitSplitter._dedupe_tasks(tasks)
        self.assertEqual(len(result), 3)
        self.assertIn("修复菜单权限", result)
        self.assertIn("优化权限逻辑", result)
        self.assertIn("添加缓存", result)

    def test_split_commits_returns_original_message(self):
        """测试 split_commits 返回原始 message"""
        classified_commits = [
            {
                'type': 'fix',
                'scope': 'perms',
                'message': '修复菜单权限，优化权限逻辑',
                'source_commit': 'abc123'
            }
        ]
        results = CommitSplitter.split_commits(classified_commits, llm_client=None)

        self.assertEqual(len(results), 1)
        # 应该包含 original_message
        self.assertIn('original_message', results[0])
        self.assertEqual(results[0]['original_message'], '修复菜单权限，优化权限逻辑')

    def test_split_commits_filters_empty_tasks(self):
        """测试 split_commits 过滤空任务列表"""
        classified_commits = [
            {
                'type': 'fix',
                'scope': 'perms',
                'message': 'x',  # 过短
                'source_commit': 'abc123'
            }
        ]
        results = CommitSplitter.split_commits(classified_commits, llm_client=None)

        # 过短的 message 会被过滤掉
        self.assertEqual(len(results), 0)

    def test_split_by_separators_edge_cases(self):
        """测试分隔符拆分的边界情况"""
        # 包含括号边界的文本
        message = "将一级菜单的 parent_code 返回值从 null 改为空字符串，addMenu兼容parent_code为null的一级菜单，确保一级菜单不传parent_code时"
        result = CommitSplitter._split_by_separators(message)

        # 应该正确拆分，不包含无效的括号
        self.assertGreater(len(result), 1)
        # 检查没有以引号或括号开头的任务
        for task in result:
            self.assertFalse(task.startswith("'"))
            self.assertFalse(task.startswith("("))
            self.assertFalse(task.startswith(")"))
            # 每个任务都应该有效（非空）
            self.assertTrue(len(task) > 0)

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

        # 禁用 V0.4 以测试 V0.3
        results = process_commits(commits, llm_client=None, enable_v04=False)

        # 应该保留 2 个
        self.assertEqual(len(results), 2)

        # 验证数据结构包含 tasks
        self.assertIn('tasks', results[0])
        self.assertIn('tasks', results[1])

        # 第一个应该被分隔符拆分
        self.assertGreater(len(results[0]['tasks']), 1)

        # 第二个应该被列表拆分
        self.assertEqual(len(results[1]['tasks']), 2)

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
        results = CommitSplitter.split_commits(classified_commits, llm_client=None)

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

        # 禁用 V0.4 以测试 V0.3 拆分
        results = process_commits(commits, llm_client=None, enable_v04=False)

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

        results = process_commits(commits, llm_client=None, enable_v04=False)

        self.assertEqual(len(results), 1)
        result = results[0]

        # 验证必需字段（V0.3 格式）
        self.assertIn('type', result)
        self.assertIn('scope', result)
        self.assertIn('tasks', result)
        self.assertIn('source_commit', result)

        # 验证 tasks 是列表
        self.assertIsInstance(result['tasks'], list)


class TestTaskAggregator(unittest.TestCase):
    """Task 聚合器测试 - V0.4"""

    def test_filter_release_words(self):
        """测试过滤发布相关词汇"""
        test_cases = [
            ("新加坡子用户改动合并德国", "子用户改动"),  # 保留"改动"
            ("德国环境配置", "配置"),
            ("巴西版本发布", ""),
            ("新加坡xxx改动", "改动"),
            ("SG环境上线", "上线"),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input=input_text):
                result = TaskAggregator._filter_release_words(input_text)
                self.assertEqual(result, expected)

    def test_generate_summary_with_status_release(self):
        """测试 release scope 的摘要生成包含状态"""
        tasks = ["新加坡子用户改动合并德国"]
        summary = TaskAggregator._generate_summary_with_status(tasks, 'release')
        # 应该包含状态
        self.assertIn('(已发布)', summary)
        # 应该过滤掉环境词，但保留"改动"
        self.assertNotIn('新加坡', summary)
        self.assertNotIn('德国', summary)
        self.assertIn('改动', summary)

    def test_aggregate_no_status_field(self):
        """测试聚合结果不包含 status 字段"""
        split_commits = [
            {'type': 'feature', 'scope': 'release', 'tasks': ['新加坡子用户改动合并德国'], 'source_commit': '001', 'original_message': '新加坡子用户改动合并德国'}
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        self.assertEqual(len(result), 1)
        # status 不应该作为独立字段存在
        self.assertNotIn('status', result[0])
        # 但 summary 应该包含状态信息
        self.assertIn('(已发布)', result[0]['summary'])

    def test_format_commit_title(self):
        """测试构造 commit 标题"""
        result = TaskAggregator._format_commit_title('fix', 'perms', '修复菜单权限问题')
        self.assertEqual(result, '[fix(perms): 修复菜单权限问题]')

    def test_type_scores(self):
        """测试类型评分常量"""
        self.assertEqual(TaskAggregator.TYPE_SCORES['feature'], 3)
        self.assertEqual(TaskAggregator.TYPE_SCORES['fix'], 2)
        self.assertEqual(TaskAggregator.TYPE_SCORES['refactor'], 1)
        self.assertEqual(TaskAggregator.MIN_SCORE, 2)

    def test_filter_by_score_keeps_high_score(self):
        """测试评分过滤保留高分项"""
        items = [
            {'type': 'feature', 'scope': 'perms', 'summary': 'abc', 'tasks': ['a', 'b'], 'source_commits': ['m1'], 'task_count': 1},
            # score = 3 * 1 = 3 >= 2, 保留
            {'type': 'fix', 'scope': 'auth', 'summary': 'def', 'tasks': ['c'], 'source_commits': ['m2'], 'task_count': 1}
            # score = 2 * 1 = 2 >= 2, 保留
        ]
        result = TaskAggregator._filter_by_score(items)
        self.assertEqual(len(result), 2)

    def test_filter_by_score_removes_low_score(self):
        """测试评分过滤移除低分项"""
        items = [
            {'type': 'refactor', 'scope': 'perms', 'summary': 'abc', 'tasks': ['a'], 'source_commits': ['m1'], 'task_count': 1}
            # score = 1 * 1 = 1 < 2, 过滤
        ]
        result = TaskAggregator._filter_by_score(items)
        self.assertEqual(len(result), 0)

    def test_merge_and_dedupe_same_scope(self):
        """测试合并相同 scope 的任务"""
        clustered = [
            {
                'type': 'fix',
                'scope': 'perms',
                'summary': '菜单 + 权限',
                'tasks': ['修复菜单权限', '优化权限'],
                'source_commits': ['msg1', 'msg2']
            },
            {
                'type': 'fix',
                'scope': 'perms',
                'summary': '权限',
                'tasks': ['修复菜单权限'],  # 重复
                'source_commits': ['msg3']
            }
        ]
        result = TaskAggregator._merge_and_dedupe(clustered)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['scope'], 'perms')
        # 应该去重
        self.assertEqual(len(result[0]['tasks']), 2)
        self.assertIn('修复菜单权限', result[0]['tasks'])
        self.assertIn('优化权限', result[0]['tasks'])

    def test_aggregate_uses_original_message(self):
        """测试聚合使用格式化的 commit 标题作为 source_commits"""
        split_commits = [
            {
                'type': 'fix',
                'scope': 'perms',
                'tasks': ['修复权限'],
                'source_commit': 'abc123',
                'original_message': '修复菜单权限问题'  # 分类后的 message 不包含前缀
            }
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        self.assertEqual(len(result), 1)
        # source_commits 应该包含格式化的 commit 标题
        self.assertIn('[fix(perms): 修复菜单权限问题]', result[0]['source_commits'])

    def test_aggregate_filters_low_score_items(self):
        """测试聚合过滤低分项"""
        split_commits = [
            {
                'type': 'refactor',
                'scope': 'utils',
                'tasks': ['小调整'],
                'source_commit': 'abc123',
                'original_message': 'refactor(utils): 小调整'
            }
            # score = 1 * 1 = 1 < 2, 应该被过滤
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        # 低分项应该被过滤
        self.assertEqual(len(result), 0)

    def test_extract_keywords_chinese(self):
        """测试提取中文关键词"""
        text = "修复菜单权限问题并优化登录逻辑"
        keywords = TaskAggregator._extract_keywords(text)
        # 应该包含匹配的技术关键词
        self.assertIn("修复", keywords)
        self.assertIn("菜单", keywords)
        self.assertIn("权限", keywords)
        self.assertIn("问题", keywords)
        self.assertIn("优化", keywords)
        self.assertIn("登录", keywords)

    def test_extract_keywords_english(self):
        """测试提取英文关键词"""
        text = "fix menu permission and optimize login"
        keywords = TaskAggregator._extract_keywords(text)
        # 英文需要至少2个字符
        self.assertIn("fix", keywords)
        self.assertIn("menu", keywords)
        self.assertIn("permission", keywords)
        self.assertIn("optimize", keywords)
        self.assertIn("login", keywords)

    def test_extract_keywords_mixed(self):
        """测试提取中英文混合关键词"""
        text = "fix菜单权限optimize"
        keywords = TaskAggregator._extract_keywords(text)
        # 应该包含英文单词和技术关键词
        self.assertIn("fix", keywords)
        self.assertIn("optimize", keywords)
        # 菜单和权限在技术关键词表中
        self.assertIn("菜单", keywords)
        self.assertIn("权限", keywords)

    def test_extract_keywords_min_length(self):
        """测试关键词最小长度过滤"""
        text = "修复a了b问题"
        keywords = TaskAggregator._extract_keywords(text)
        # 单个字符的英文应该被过滤
        self.assertIn("修复", keywords)
        self.assertIn("问题", keywords)
        self.assertNotIn("a", keywords)
        self.assertNotIn("b", keywords)

    def test_compute_similarity_jaccard(self):
        """测试 Jaccard 相似度计算"""
        set1 = {"菜单", "权限", "修复"}
        set2 = {"菜单", "权限", "优化"}
        # 交集: {菜单, 权限} = 2, 并集: {菜单, 权限, 修复, 优化} = 4
        # 相似度 = 2/4 = 0.5
        similarity = TaskAggregator._compute_similarity(set1, set2)
        self.assertAlmostEqual(similarity, 0.5, places=2)

    def test_compute_similarity_identical(self):
        """测试相同集合的相似度为1"""
        set1 = {"菜单", "权限"}
        set2 = {"菜单", "权限"}
        similarity = TaskAggregator._compute_similarity(set1, set2)
        self.assertEqual(similarity, 1.0)

    def test_compute_similarity_disjoint(self):
        """测试无交集集合的相似度为0"""
        set1 = {"菜单", "权限"}
        set2 = {"登录", "缓存"}
        similarity = TaskAggregator._compute_similarity(set1, set2)
        self.assertEqual(similarity, 0.0)

    def test_compute_similarity_empty_sets(self):
        """测试空集合的相似度为0"""
        similarity = TaskAggregator._compute_similarity(set(), set())
        self.assertEqual(similarity, 0.0)

    def test_group_by_type_scope(self):
        """测试按 type + scope 分组"""
        split_commits = [
            {'type': 'fix', 'scope': 'perms', 'tasks': ['修复权限'], 'source_commit': '001'},
            {'type': 'fix', 'scope': 'perms', 'tasks': ['优化权限'], 'source_commit': '002'},
            {'type': 'feat', 'scope': 'auth', 'tasks': ['添加登录'], 'source_commit': '003'},
            {'type': 'fix', 'scope': 'auth', 'tasks': ['修复登录'], 'source_commit': '004'},
        ]
        groups = TaskAggregator._group_by_type_scope(split_commits)

        self.assertEqual(len(groups), 3)  # fix/perms, feat/auth, fix/auth
        self.assertIn('fix/perms', groups)
        self.assertIn('feat/auth', groups)
        self.assertIn('fix/auth', groups)
        self.assertEqual(len(groups['fix/perms']), 2)
        self.assertEqual(len(groups['feat/auth']), 1)

    def test_aggregate_single_commit(self):
        """测试单个 commit 的聚合"""
        split_commits = [
            {'type': 'fix', 'scope': 'perms', 'tasks': ['修复菜单权限问题'], 'source_commit': '001', 'original_message': '修复菜单权限问题'}
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['type'], 'fix')
        self.assertEqual(result[0]['scope'], 'perms')
        self.assertEqual(len(result[0]['tasks']), 1)
        self.assertEqual(result[0]['task_count'], 1)
        self.assertIn('summary', result[0])
        self.assertIn('source_commits', result[0])
        # 验证 source_commits 格式
        self.assertIn('[fix(perms): 修复菜单权限问题]', result[0]['source_commits'])

    def test_aggregate_similar_tasks(self):
        """测试相似任务的聚合"""
        split_commits = [
            {'type': 'fix', 'scope': 'perms', 'tasks': ['修复菜单权限问题'], 'source_commit': '001', 'original_message': 'm1'},
            {'type': 'fix', 'scope': 'perms', 'tasks': ['优化菜单权限逻辑'], 'source_commit': '002', 'original_message': 'm2'},
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        # 由于关键词相似，应该聚合成一个组
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['task_count'], 2)
        self.assertEqual(len(result[0]['source_commits']), 2)

    def test_aggregate_different_scopes(self):
        """测试不同 scope 的任务不聚合"""
        split_commits = [
            {'type': 'fix', 'scope': 'perms', 'tasks': ['修复权限问题'], 'source_commit': '001', 'original_message': 'm1'},
            {'type': 'fix', 'scope': 'auth', 'tasks': ['修复权限问题'], 'source_commit': '002', 'original_message': 'm2'},
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        # 不同 scope 不应该聚合
        self.assertEqual(len(result), 2)

    def test_aggregate_structure(self):
        """测试聚合结果的数据结构"""
        split_commits = [
            {'type': 'fix', 'scope': 'perms', 'tasks': ['修复权限'], 'source_commit': '001', 'original_message': 'm1'}
        ]
        result = TaskAggregator.aggregate(split_commits, llm_client=None)

        item = result[0]
        # 验证所有必需字段（不包含 status 字段）
        self.assertIn('type', item)
        self.assertIn('scope', item)
        self.assertIn('summary', item)
        self.assertIn('tasks', item)
        self.assertIn('source_commits', item)
        self.assertIn('task_count', item)
        # 确保没有 status 字段
        self.assertNotIn('status', item)

        # 验证类型
        self.assertIsInstance(item['tasks'], list)
        self.assertIsInstance(item['source_commits'], list)
        self.assertIsInstance(item['task_count'], int)

        # 验证 summary 包含状态（如果检测到）
        if '发布' in split_commits[0]['tasks'][0]:
            self.assertIn('(已发布)', item['summary'])


class TestProcessCommitsV04(unittest.TestCase):
    """完整处理流程测试 - V0.4"""

    def test_process_commits_with_aggregation(self):
        """测试完整流程：过滤 -> 分类 -> 拆分 -> 聚合"""
        commits = [
            {"hash": "001", "message": "fix(perms): 修复菜单权限"},
            {"hash": "002", "message": "fix(perms): 优化菜单权限逻辑"},
            {"hash": "003", "message": "feat(auth): 添加登录功能"},
        ]
        results = process_commits(commits, llm_client=None, enable_v04=True)

        # V0.4 聚合后，前两个应该聚合在一起
        self.assertGreater(len(results), 0)

        # 验证 V0.4 数据结构
        for result in results:
            self.assertIn('type', result)
            self.assertIn('scope', result)
            self.assertIn('summary', result)
            self.assertIn('tasks', result)
            self.assertIn('source_commits', result)
            self.assertIn('task_count', result)

    def test_process_commits_disable_v04(self):
        """测试禁用 V0.4 聚合"""
        commits = [
            {"hash": "001", "message": "fix(perms): 修复菜单权限，优化权限逻辑"},
        ]
        results = process_commits(commits, llm_client=None, enable_v04=False)

        # 禁用 V0.4 时，不应该有 summary 和 source_commits 字段
        self.assertEqual(len(results), 1)
        self.assertNotIn('summary', results[0])
        self.assertIn('source_commit', results[0])  # V0.3 用单数形式

    def test_process_commits_enable_v04(self):
        """测试启用 V0.4 聚合"""
        commits = [
            {"hash": "001", "message": "fix(perms): 修复菜单权限，优化权限逻辑"},
        ]
        results = process_commits(commits, llm_client=None, enable_v04=True)

        # 启用 V0.4 时，应该有 V0.4 的字段
        self.assertEqual(len(results), 1)
        self.assertIn('summary', results[0])
        self.assertIn('source_commits', results[0])  # V0.4 用复数形式
        self.assertIn('task_count', results[0])


if __name__ == '__main__':
    unittest.main()
