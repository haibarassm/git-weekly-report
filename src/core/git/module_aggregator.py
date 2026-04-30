"""模块聚合器 - 按模块聚合分类结果"""
import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class ModuleAggregator:
    """按模块聚合 DefaultCommitClassifier 的分类结果

    输入: [{module, action, confidence, message, hash}]
    输出: [{name, count, actions, sample_messages}]
    """

    CONFIDENCE_THRESHOLD = 0.4
    MIN_TASK_COUNT = 2  # 最小任务数，少于 2 个任务的模块不进入简历

    @classmethod
    def aggregate(cls, classified_results: List[Dict], modules: List[Dict] = None) -> List[Dict]:
        """聚合分类结果

        Args:
            classified_results: DefaultCommitClassifier.classify_batch 的输出
            modules: 模块配置 [{name, keywords}]，未使用（保留参数兼容性）

        Returns:
            [{name, count, actions, sample_messages}]
        """
        # 按模块分组
        module_stats = defaultdict(lambda: {"count": 0, "actions": set(), "sample_messages": []})

        unknown_count = 0
        low_confidence_count = 0

        for item in classified_results:
            module = item.get("module", "unknown")
            confidence = item.get("confidence", 0.0)
            action = item.get("action", "开发")
            message = item.get("message", "")

            # 过滤低置信度
            if confidence < cls.CONFIDENCE_THRESHOLD and module != "unknown":
                low_confidence_count += 1
                continue

            # 过滤 unknown（舍弃，不使用 LLM 处理）
            if module == "unknown":
                unknown_count += 1
                continue

            module_stats[module]["count"] += 1
            module_stats[module]["actions"].add(action)

            # 保留前 3 条 sample message
            if len(module_stats[module]["sample_messages"]) < 3:
                module_stats[module]["sample_messages"].append(message[:80])

        # 转换为列表，按 count 降序，并过滤 task_count < 2 的模块
        results = []
        filtered_count = 0
        for name, stats in sorted(module_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            # 过滤任务数少于 MIN_TASK_COUNT 的模块
            if stats["count"] < cls.MIN_TASK_COUNT:
                filtered_count += 1
                logger.info(f"  [聚合] 过滤低频模块: {name} ({stats['count']} 条 < {cls.MIN_TASK_COUNT})")
                continue

            results.append({
                "name": name,
                "count": stats["count"],
                "actions": list(stats["actions"]),
                "sample_messages": stats["sample_messages"]
            })

        logger.info(f"  [聚合] 完成: {len(results)} 个有效模块 (unknown={unknown_count}, low_confidence={low_confidence_count}, filtered={filtered_count})")
        for r in results:
            logger.info(f"    - {r['name']}: {r['count']} 条, actions={r['actions']}")

        return results
