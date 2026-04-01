"""Commit 处理模块

版本迭代:
- V0.2: 过滤 + 分类
- V0.3: V0.2 + 拆分
"""
import re
import json
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
    tasks: List[str]  # V0.3: 拆分后的任务列表 (V0.2 时为单元素列表)
    source_commit: str

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


# =============================================================================
# V0.2: 过滤与分类
# =============================================================================

class CommitFilterV02:
    """Commit 过滤器 - V0.2"""

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


class CommitClassifierV02:
    """Commit 分类器 - V0.2"""

    CONVENTIONAL_COMMIT_PATTERN = re.compile(r'^(\w+)\(([^)]+)\)\s*:\s*(.+)$', re.DOTALL)
    SIMPLE_TYPE_PATTERN = re.compile(r'^(\w+)\s*:\s*(.+)$', re.DOTALL)

    FEAT_KEYWORDS = ["发布", "上线", "新加坡", "德国", "巴西"]
    FIX_KEYWORDS = ["修复", "bug", "问题"]

    @classmethod
    def _parse_standard_format(cls, message: str) -> Optional[Tuple[str, str, str]]:
        """解析标准格式 commit，返回 (type, scope, message) 或 None"""
        match = cls.CONVENTIONAL_COMMIT_PATTERN.match(message)
        if match:
            return match.groups()
        match = cls.SIMPLE_TYPE_PATTERN.match(message)
        if match:
            return (match.group(1), "default", match.group(2))
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
                'message': result.tasks[0],  # 保留 message 供 V0.3 拆分使用
                'source_commit': result.source_commit
            })
            logger.debug(f"  [{result.type}/{result.scope}] {result.source_commit[:7]}")

        return results


# =============================================================================
# V0.3: 拆分
# =============================================================================

class CommitSplitterV03:
    """Commit 拆分器 - V0.3

    拆分优先级:
    1. Markdown 格式 (## 标题 + 1. 2. 编号)
    2. - 列表格式
    3. 普通文本分隔符 (， , and + 以及)
    4. LLM 兜底拆分
    """

    TEXT_SEPARATORS = ['，', ',', ' and ', '+', '以及']
    LLM_SPLIT_MIN_LENGTH = 15
    LLM_MAX_TASKS = 5

    @classmethod
    def _split_markdown(cls, message: str) -> Optional[List[str]]:
        """拆分 Markdown 格式"""
        if "##" not in message:
            return None

        tasks = []
        blocks = message.split("##")

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            numbered_items = re.split(r'\n\s*\d+[.、]\s*', block)
            for item in numbered_items:
                item = item.strip()
                if item and len(item) > 2:
                    tasks.append(item)

        return tasks if tasks else None

    @classmethod
    def _split_dash_list(cls, message: str) -> Optional[List[str]]:
        """拆分 - 列表格式"""
        lines = message.strip().split('\n')
        tasks = []

        for line in lines:
            line = line.strip()
            if line.startswith('- '):
                task = line[2:].strip()
                if task:
                    tasks.append(task)
            elif line.startswith('-'):
                task = line[1:].strip()
                if task:
                    tasks.append(task)

        return tasks if tasks else None

    @classmethod
    def _split_by_separators(cls, message: str) -> List[str]:
        """按分隔符拆分普通文本"""
        import re
        tasks = []
        lines = message.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            sep_pattern = '|'.join(re.escape(sep) for sep in cls.TEXT_SEPARATORS)
            parts = re.split(sep_pattern, line)
            for part in parts:
                part = part.strip()
                if part and len(part) > 2:
                    tasks.append(part)

        return tasks if tasks else [message.strip()]

    @classmethod
    def _count_sentences(cls, text: str) -> int:
        """统计句子数量"""
        sentences = re.split(r'[。.！!?？]', text)
        return len([s for s in sentences if s.strip()])

    @classmethod
    def split_by_llm(cls, message: str, llm_client=None) -> List[str]:
        """使用 LLM 拆分 commit"""
        import logging
        logger = logging.getLogger(__name__)

        if llm_client is None:
            return [message.strip()]

        prompt = f"""请将以下 commit 消息拆分为多个独立的任务（最多 {cls.LLM_MAX_TASKS} 个）。

要求：
1. 每个任务应该是独立可理解的功能点
2. 保持原意不变
3. 只返回任务列表，每行一个任务
4. 如果无法拆分，直接返回原文

Commit 消息：
{message}

任务列表："""

        try:
            response = llm_client.generate(prompt)
            tasks = [line.strip() for line in response.split('\n') if line.strip()]
            if len(tasks) > cls.LLM_MAX_TASKS:
                tasks = tasks[:cls.LLM_MAX_TASKS]
            if tasks:
                return tasks
            return [message.strip()]
        except Exception as e:
            logging.getLogger(__name__).warning(f"LLM 拆分失败: {e}")
            return [message.strip()]

    @classmethod
    def split(cls, classified_commit: Dict, llm_client=None) -> List[str]:
        """对分类后的 commit 进行拆分"""
        import logging
        logger = logging.getLogger(__name__)

        message = classified_commit.get('message', '')
        if not message:
            return []

        # 规则1: Markdown 格式
        markdown_tasks = cls._split_markdown(message)
        if markdown_tasks and len(markdown_tasks) > 1:
            return markdown_tasks

        # 规则2: - 列表
        dash_tasks = cls._split_dash_list(message)
        if dash_tasks and len(dash_tasks) > 1:
            return dash_tasks

        # 规则3: 分隔符
        separator_tasks = cls._split_by_separators(message)
        if len(separator_tasks) > 1:
            return separator_tasks

        # 规则4: LLM 兜底
        sentence_count = cls._count_sentences(message)
        message_length = len(message.strip())
        if sentence_count <= 1 and message_length > cls.LLM_SPLIT_MIN_LENGTH:
            return cls.split_by_llm(message, llm_client)

        return [message.strip()]

    @classmethod
    def split_commits(cls, classified_commits: List[Dict], llm_client=None) -> List[Dict]:
        """对分类后的 commit 列表进行拆分"""
        import logging
        logger = logging.getLogger(__name__)

        results = []
        for commit in classified_commits:
            tasks = cls.split(commit, llm_client)
            results.append({
                'type': commit.get('type', 'refactor'),
                'scope': commit.get('scope', 'default'),
                'tasks': tasks,
                'source_commit': commit.get('source_commit', '')
            })

        return results


# =============================================================================
# 完整处理流程
# =============================================================================

def process_commits(commits: List[Dict], llm_client=None) -> List[Dict]:
    """
    完整处理流程：过滤 -> 分类 -> 拆分

    Args:
        commits: 原始 commit 列表
        llm_client: LLM 客户端（可选，用于 V0.3 拆分）

    Returns:
        处理后的 commit 列表，结构:
        [
            {
                "type": "fix",
                "scope": "perms",
                "tasks": ["修复菜单权限问题", "优化权限逻辑"],
                "source_commit": "abc123"
            },
            ...
        ]
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info(f"Commit 处理开始: {len(commits)} 条原始 commit")
    logger.info("=" * 50)

    # V0.2: 步骤1 - 过滤
    filtered, filter_stats = CommitFilterV02.filter_commits(commits)
    logger.info(f"[V0.2 过滤] 保留 {len(filtered)} 条，过滤 {len(commits) - len(filtered)} 条")

    # V0.2: 步骤2 - 分类
    classified = CommitClassifierV02.classify_commits(filtered)
    type_count = {}
    for c in classified:
        t = c.get('type', 'unknown')
        type_count[t] = type_count.get(t, 0) + 1
    logger.info(f"[V0.2 分类] {type_count}")

    # V0.3: 步骤3 - 拆分
    split = CommitSplitterV03.split_commits(classified, llm_client)
    total_tasks = sum(len(c['tasks']) for c in split)
    logger.info(f"[V0.3 拆分] {len(split)} 个 commit -> {total_tasks} 个任务")

    # 输出最终 JSON 结构
    logger.info("=" * 50)
    logger.info(">>> 最终 JSON 结构 (传给 LLM):")
    logger.info(json.dumps(split, ensure_ascii=False, indent=2))
    logger.info("=" * 50)

    return split
