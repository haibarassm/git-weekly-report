"""Commit 聚合器 - 按项目/类型聚合任务"""
from typing import List, Dict
from collections import Counter


class CommitAggregator:
    """Commit 聚合器 - 按项目 ID / type / scope 聚合

    聚合策略:
    1. 按 type + scope 分组
    2. 合并相同 tasks，去重
    """

    @classmethod
    def aggregate(
        cls,
        classified_commits: List[Dict],
        project_id: str = None
    ) -> List[Dict]:
        """聚合已分类的 commits

        Args:
            classified_commits: 分类后的 commit 列表
            project_id: 项目 ID（可选，用于简历场景）

        Returns:
            聚合后的任务列表
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f">>> [聚合] 开始聚合 {len(classified_commits)} 个 commits")

        # 按 type + scope 分组
        groups = {}
        for commit in classified_commits:
            key = f"{commit.get('type', 'refactor')}/{commit.get('scope', 'default')}"
            if key not in groups:
                groups[key] = {
                    'type': commit.get('type', 'refactor'),
                    'scope': commit.get('scope', 'default'),
                    'tasks': set(),
                    'source_commits': [],
                    'original_messages': []
                }

            # 添加任务
            for task in commit.get('tasks', []):
                groups[key]['tasks'].add(task)

            # 添加源 commit
            if commit.get('source_commit'):
                groups[key]['source_commits'].append(commit.get('source_commit'))

            # 添加原始消息
            if commit.get('original_message'):
                groups[key]['original_messages'].append(commit.get('original_message'))

        # 转换为列表
        results = []
        for key, group in groups.items():
            results.append({
                'type': group['type'],
                'scope': group['scope'],
                'tasks': list(group['tasks']),
                'source_commits': group['source_commits'],
                'original_messages': group['original_messages'],
                'task_count': len(group['tasks'])
            })
            logger.info(f"  [{key}] {len(group['tasks'])} 个任务")

        logger.info(f">>> [聚合] 完成，共 {len(results)} 个聚合组")
        return results
