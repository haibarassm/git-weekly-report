"""Commit 处理模块包

处理步骤:
1. 过滤 (filter) - 过滤无效 commit
2. 分类 (classifier) - 按 type/scope 分类
3. 拆分 (splitter) - 拆分为细粒度任务
4. 聚合 (aggregator) - 聚合为高层任务
"""

from .common import CommitType, ClassifiedCommit
from .filter_classifier import CommitFilter, CommitClassifier
from .splitter import CommitSplitter
from .aggregator import TaskAggregator
from .processor import process_commits

__all__ = [
    # Common
    'CommitType',
    'ClassifiedCommit',
    # Step 1-2: Filter & Classifier
    'CommitFilter',
    'CommitClassifier',
    # Step 3: Splitter
    'CommitSplitter',
    # Step 4: Aggregator
    'TaskAggregator',
    # Main
    'process_commits',
]
