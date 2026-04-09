"""Commit 处理模块 - 通用数据结构"""
from typing import List, Dict
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
