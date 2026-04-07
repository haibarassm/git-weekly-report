"""Commit 处理模块 - 主处理流程"""
import json
from typing import List, Dict

from .filter_classifier import CommitFilter, CommitClassifier
from .splitter import CommitSplitter
from .aggregator import TaskAggregator


def process_commits(commits: List[Dict], llm_client=None, enable_v04: bool = True) -> List[Dict]:
    """
    完整处理流程：过滤 -> 分类 -> 拆分 -> 聚合

    Args:
        commits: 原始 commit 列表
        llm_client: LLM 客户端（可选，用于拆分和摘要）
        enable_v04: 是否启用聚合（默认 True）

    Returns:
        处理后的 commit 列表，聚合结构:
        [
            {
                "type": "fix",
                "scope": "perms",
                "summary": "权限管理优化",
                "tasks": ["修复菜单权限", "优化角色权限"],
                "source_commits": ["abc123", "def456"],
                "task_count": 2
            },
            ...
        ]
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info(f"Commit 处理开始: {len(commits)} 条原始 commit")
    logger.info("=" * 60)

    # 步骤1: 过滤
    filtered, filter_stats = CommitFilter.filter_commits(commits)
    logger.info(f">>> 步骤1: [过滤] 保留 {len(filtered)} 条，过滤 {len(commits) - len(filtered)} 条")

    # 步骤2: 分类
    classified = CommitClassifier.classify_commits(filtered)
    type_count = {}
    for c in classified:
        t = c.get('type', 'unknown')
        type_count[t] = type_count.get(t, 0) + 1
    logger.info(f">>> 步骤2: [分类] {type_count}")

    # 步骤3: 拆分
    split = CommitSplitter.split_commits(classified, llm_client)
    total_tasks = sum(len(c['tasks']) for c in split)
    logger.info(f">>> 步骤3: [拆分] {len(split)} 个 commit -> {total_tasks} 个任务")

    # 步骤4: 聚合
    if enable_v04:
        aggregated = TaskAggregator.aggregate(split, llm_client)
        logger.info(f">>> 步骤4: [聚合] 完成，共 {len(aggregated)} 个聚合组")
        result = aggregated
    else:
        result = split

    # 输出最终 JSON 结构
    logger.info("=" * 60)
    logger.info(">>> 最终 JSON 结构 (传给 LLM):")
    logger.info(json.dumps(result, ensure_ascii=False, indent=2))
    logger.info("=" * 60)

    return result
