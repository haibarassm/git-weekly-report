"""Commit 处理模块 - V0.2 过滤与分类"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class CommitType(Enum):
    """Commit 类型枚举"""
    FEAT = "feature"
    FIX = "fix"
    REFACTOR = "refactor"


@dataclass
class ClassifiedCommit:
    """分类后的 Commit 数据结构"""
    type: str
    scope: str
    message: str
    source_commit: str

    def to_dict(self) -> Dict[str, str]:
        """转换为字典"""
        return asdict(self)


class CommitFilter:
    """Commit 过滤器 - V0.2"""

    # 过滤关键词
    FILTER_PATTERNS = [
        "Merge branch",
        "test",
    ]

    # 最小消息长度
    MIN_MESSAGE_LENGTH = 5

    @classmethod
    def should_filter(cls, commit_message: str) -> tuple[bool, str]:
        """
        判断 commit 是否应该被过滤

        Args:
            commit_message: commit 消息

        Returns:
            (是否过滤, 过滤原因)
        """
        # 规则1: 包含 "Merge branch"
        if "Merge branch" in commit_message:
            return True, "Merge branch"

        # 规则2: 包含 "test"
        if "test" in commit_message:
            return True, "包含test"

        # 规则3: message 长度 < 5
        stripped = commit_message.strip()
        if len(stripped) < cls.MIN_MESSAGE_LENGTH:
            return True, f"长度<5 (实际{len(stripped)}字符)"

        return False, ""

    @classmethod
    def filter_commits(cls, commits: List[Dict]) -> List[Dict]:
        """
        过滤 commit 列表

        Args:
            commits: commit 列表

        Returns:
            过滤后的 commit 列表
        """
        import logging
        logger = logging.getLogger(__name__)

        filtered = []
        filter_stats = {}

        for commit in commits:
            should_filt, reason = cls.should_filter(commit['message'])
            if should_filt:
                filter_stats[reason] = filter_stats.get(reason, 0) + 1
                commit_hash = commit.get('hash', '')[:7]
                logger.info(f"  [过滤] {commit_hash} | {reason} | {commit['message'][:60]}")
            else:
                filtered.append(commit)

        logger.info(f"过滤统计: {filter_stats}")
        return filtered


class CommitClassifier:
    """Commit 分类器 - V0.2"""

    # 标准格式正则表达式
    CONVENTIONAL_COMMIT_PATTERN = re.compile(
        r'^(\w+)\(([^)]+)\)\s*:\s*(.+)$'
    )

    # 简化格式正则表达式 (只有 type)
    SIMPLE_TYPE_PATTERN = re.compile(
        r'^(\w+)\s*:\s*(.+)$'
    )

    # feat 关键词（发布相关）
    FEAT_KEYWORDS = [
        "发布", "上线", "新加坡", "德国", "巴西"
    ]

    # fix 关键词（修复相关）
    FIX_KEYWORDS = [
        "修复", "bug", "问题"
    ]

    @classmethod
    def _parse_standard_format(cls, message: str) -> Optional[Tuple[str, str, str]]:
        """
        解析标准格式 commit

        Args:
            message: commit 消息

        Returns:
            (type, scope, cleaned_message) 或 None
        """
        # 尝试匹配 type(scope): message
        match = cls.CONVENTIONAL_COMMIT_PATTERN.match(message)
        if match:
            commit_type, scope, cleaned_message = match.groups()
            return (commit_type, scope, cleaned_message)

        # 尝试匹配 type: message
        match = cls.SIMPLE_TYPE_PATTERN.match(message)
        if match:
            commit_type, cleaned_message = match.groups()
            return (commit_type, "default", cleaned_message)

        return None

    @classmethod
    def _classify_by_keywords(cls, message: str) -> str:
        """
        根据关键词对无格式 commit 进行分类

        Args:
            message: commit 消息

        Returns:
            Commit 类型
        """
        # 检查 feat 关键词
        for keyword in cls.FEAT_KEYWORDS:
            if keyword in message:
                return CommitType.FEAT.value

        # 检查 fix 关键词
        for keyword in cls.FIX_KEYWORDS:
            if keyword in message:
                return CommitType.FIX.value

        # 默认为 refactor
        return CommitType.REFACTOR.value

    @classmethod
    def _extract_scope(cls, message: str) -> str:
        """
        提取 scope

        Args:
            message: commit 消息

        Returns:
            scope 字符串
        """
        # 尝试匹配括号内容
        match = re.search(r'\(([^)]+)\)', message)
        if match:
            return match.group(1)

        return "default"

    @classmethod
    def _normalize_type(cls, commit_type: str) -> str:
        """
        标准化 type

        Args:
            commit_type: 原始 type

        Returns:
            标准化后的 type
        """
        type_mapping = {
            "feat": CommitType.FEAT.value,
            "feature": CommitType.FEAT.value,
            "fix": CommitType.FIX.value,
            "refactor": CommitType.REFACTOR.value,
        }
        return type_mapping.get(commit_type.lower(), CommitType.REFACTOR.value)

    @classmethod
    def classify(cls, commit: Dict) -> ClassifiedCommit:
        """
        对单个 commit 进行分类

        Args:
            commit: commit 数据字典

        Returns:
            ClassifiedCommit 对象
        """
        import logging
        logger = logging.getLogger(__name__)

        message = commit['message']
        source_commit = commit.get('hash', '')

        # 首先尝试解析标准格式
        standard_format = cls._parse_standard_format(message)
        if standard_format:
            commit_type, scope, cleaned_message = standard_format
            normalized_type = cls._normalize_type(commit_type)
            logger.debug(f"  解析: [{commit_type}] -> [{normalized_type}]")
            return ClassifiedCommit(
                type=normalized_type,
                scope=scope,
                message=cleaned_message,
                source_commit=source_commit
            )

        # 无格式 commit - 使用关键词分类
        commit_type = cls._classify_by_keywords(message)
        scope = cls._extract_scope(message)
        logger.debug(f"  关键词: [{commit_type}/{scope}]")

        return ClassifiedCommit(
            type=commit_type,
            scope=scope,
            message=message,
            source_commit=source_commit
        )

    @classmethod
    def classify_commits(cls, commits: List[Dict]) -> List[Dict]:
        """
        对 commit 列表进行分类

        Args:
            commits: commit 列表

        Returns:
            分类后的 commit 列表（字典格式）
        """
        import logging
        logger = logging.getLogger(__name__)

        classified = []
        for commit in commits:
            result = cls.classify(commit)
            classified.append(result.to_dict())
            # 记录分类结果
            commit_hash = commit.get('hash', '')[:7]
            logger.info(f"  [{result.type}/{result.scope}] {commit_hash} | {result.message[:60]}")

        return classified


def process_commits(commits: List[Dict]) -> List[Dict]:
    """
    完整处理流程：过滤 -> 分类

    Args:
        commits: 原始 commit 列表

    Returns:
        处理后的 commit 列表
    """
    import logging
    logger = logging.getLogger(__name__)

    # 步骤1: 过滤
    filtered = CommitFilter.filter_commits(commits)

    # 步骤2: 分类
    logger.info(">>> 步骤2: 分类 commit")
    classified = CommitClassifier.classify_commits(filtered)

    return classified
