"""Commit 分类器 - 按 type/scope 分类"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
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
    tasks: List[str]
    source_commit: str


class CommitFilter:
    """Commit 过滤器 - 过滤无效 commit"""

    FILTER_PATTERNS = ["Merge branch", "test"]
    MIN_MESSAGE_LENGTH = 5

    @classmethod
    def should_filter(cls, commit_message: str) -> tuple[bool, str]:
        """判断 commit 是否应该被过滤"""
        if "Merge branch" in commit_message:
            return True, "Merge branch"
        if "test" in commit_message:
            return True, "包含test"
        stripped = commit_message.strip()
        if len(stripped) < cls.MIN_MESSAGE_LENGTH:
            return True, f"长度<5"
        return False, ""

    @classmethod
    def filter_commits(cls, commits: List[Dict]) -> tuple[List[Dict], Dict[str, int]]:
        """过滤 commit 列表，返回 (过滤后的列表, 过滤统计)"""
        import logging
        logger = logging.getLogger(__name__)

        filtered = []
        filter_stats = {}

        for commit in commits:
            should_filt, reason = cls.should_filter(commit['message'])
            if should_filt:
                filter_stats[reason] = filter_stats.get(reason, 0) + 1
                logger.debug(f"  [过滤] {commit.get('hash', '')[:7]} | {reason}")
            else:
                filtered.append(commit)

        return filtered, filter_stats


class TaskClassifier:
    """Commit 分类器 - 按 type/scope 分类"""

    CONVENTIONAL_COMMIT_PATTERN = re.compile(r'^(\w+)\(([^)]+)\)\s*:\s*(.+)$', re.DOTALL)
    SIMPLE_TYPE_PATTERN = re.compile(r'^(\w+)\s*:\s*(.+)$', re.DOTALL)

    # 特殊 scope：发布相关
    RELEASE_SCOPE = "release"
    RELEASE_KEYWORDS = ["发布", "上线", "新加坡", "德国", "巴西"]

    FEAT_KEYWORDS = ["发布", "上线", "新加坡", "德国", "巴西"]
    FIX_KEYWORDS = ["修复", "bug", "问题"]

    @classmethod
    def _is_release_commit(cls, message: str) -> bool:
        """判断是否是发布相关的 commit"""
        for keyword in cls.RELEASE_KEYWORDS:
            if keyword in message:
                return True
        return False

    @classmethod
    def _parse_standard_format(cls, message: str) -> Optional[Tuple[str, str, str]]:
        """解析标准格式 commit，返回 (type, scope, message) 或 None"""
        match = cls.CONVENTIONAL_COMMIT_PATTERN.match(message)
        if match:
            return match.groups()
        match = cls.SIMPLE_TYPE_PATTERN.match(message)
        if match:
            commit_type, msg = match.groups()
            # 检查是否是发布相关，使用特殊 scope
            if cls._is_release_commit(msg):
                return (commit_type, cls.RELEASE_SCOPE, msg)
            return (commit_type, "default", msg)
        return None

    @classmethod
    def _classify_by_keywords(cls, message: str) -> str:
        """根据关键词分类"""
        for keyword in cls.FEAT_KEYWORDS:
            if keyword in message:
                return CommitType.FEAT.value
        for keyword in cls.FIX_KEYWORDS:
            if keyword in message:
                return CommitType.FIX.value
        return CommitType.REFACTOR.value

    @classmethod
    def _normalize_type(cls, commit_type: str) -> str:
        """标准化 type"""
        type_mapping = {
            "feat": CommitType.FEAT.value,
            "feature": CommitType.FEAT.value,
            "fix": CommitType.FIX.value,
            "refactor": CommitType.REFACTOR.value,
        }
        return type_mapping.get(commit_type.lower(), CommitType.REFACTOR.value)

    @classmethod
    def classify(cls, commit: Dict) -> ClassifiedCommit:
        """对单个 commit 进行分类，返回 ClassifiedCommit"""
        message = commit['message']
        source_commit = commit.get('hash', '')

        # 尝试解析标准格式
        standard_format = cls._parse_standard_format(message)
        if standard_format:
            commit_type, scope, cleaned_message = standard_format
            normalized_type = cls._normalize_type(commit_type)
            return ClassifiedCommit(
                type=normalized_type,
                scope=scope,
                tasks=[cleaned_message],
                source_commit=source_commit
            )

        # 关键词分类
        commit_type = cls._classify_by_keywords(message)

        # 检查是否是发布相关，使用特殊 scope
        if cls._is_release_commit(message):
            return ClassifiedCommit(
                type=CommitType.FEAT.value,
                scope=cls.RELEASE_SCOPE,
                tasks=[message],
                source_commit=source_commit
            )

        return ClassifiedCommit(
            type=commit_type,
            scope="default",
            tasks=[message],
            source_commit=source_commit
        )

    @classmethod
    def classify_commits(cls, commits: List[Dict]) -> List[Dict]:
        """对 commit 列表进行分类"""
        import logging
        logger = logging.getLogger(__name__)

        results = []
        for commit in commits:
            result = cls.classify(commit)
            results.append({
                'type': result.type,
                'scope': result.scope,
                'message': result.tasks[0],  # 保留 message 供拆分使用
                'source_commit': result.source_commit
            })
            logger.debug(f"  [{result.type}/{result.scope}] {result.source_commit[:7]}")

        return results
