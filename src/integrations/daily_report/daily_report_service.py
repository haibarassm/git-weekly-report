"""日报生成服务 - 复用周报管线，切换到日报提示词与规则

与周报的差异（mode="daily"）：
- 默认 1 天
- 无状态枚举（对接中/已提测/已发布）
- 不限条数
- 同模块 commits 合并成一条

周报逻辑完全不受影响（generate_report 的 simple/professional 路径不变）。
"""
from pathlib import Path
from typing import Optional, Tuple

from ..git_report.report_service import ReportService


class DailyReportService(ReportService):
    """日报生成服务

    复用周报的整条管线（CommitFetcher → 过滤 → 分类 → 拆分 → 聚合 → ContentGenerationWorkflow），
    通过 mode="daily" 让 workflow 加载日报专属提示词（daily_report/）：
    - generator 走 daily_report/generator_simple.txt（无状态/不限条数/合并同模块）
    - reviewer 走 daily_report/reviewer.txt（放松审查，不强制状态与字数）
    """

    def __init__(self, config=None):
        # ReportService 内部用全局 config，这里接受 config 仅为和其它 tab 的构造约定对齐
        super().__init__()

    def generate_daily(
        self,
        selected_branches: list[str],
        days: int = 1,
    ) -> Tuple[str, Optional[Path]]:
        """生成日报

        Args:
            selected_branches: 已选分支列表（格式：项目路径/分支名）
            days: 取近几天，默认 1（当天）

        Returns:
            (日报内容, 文件路径) 或 (错误信息, None)
        """
        return self.generate_report(
            selected_branches=selected_branches,
            days=days,
            mode="daily",
        )
