"""Commit 处理模块 - 向后兼容接口

此文件保留用于向后兼容，实际代码已拆分到 commit_processor 包中。
新代码应该直接从 commit_processor 包导入：
    from commit_processor import process_commits, TaskAggregator, ...

版本迭代:
- V0.2: 过滤 + 分类
- V0.3: V0.2 + 拆分
- V0.4: V0.3 + 聚合
"""

# 从包中导入所有公共接口
from .commit_processor import (
    # Common
    CommitType,
    ClassifiedCommit,
    # V0.2
    CommitFilterV02,
    CommitClassifierV02,
    # V0.3
    CommitSplitterV03,
    # V0.4
    TaskAggregator,
    # Main
    process_commits,
)

__all__ = [
    # Common
    'CommitType',
    'ClassifiedCommit',
    # V0.2
    'CommitFilterV02',
    'CommitClassifierV02',
    # V0.3
    'CommitSplitterV03',
    # V0.4
    'TaskAggregator',
    # Main
    'process_commits',
]
