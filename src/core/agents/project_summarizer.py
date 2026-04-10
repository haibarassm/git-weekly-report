"""项目总结 Agent - 压缩大量 commit 信息"""
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import json
import logging

from src.core.llm.client import get_llm_client


@dataclass
class ProjectSummary:
    """项目摘要"""
    project_id: str
    technical_highlights: str
    key_achievements: List[str]
    main_contributions: List[str]


class ProjectSummarizerAgent:
    """将大量 commit 信息压缩成结构化摘要

    用于简历生成场景，将项目的所有提交记录压缩为：
    - 技术亮点（2-3 句话）
    - 关键成果（3-5 条）
    - 主要贡献（按模块分类）
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "resume" / "project_summarizer.txt"

    def __init__(self):
        self.llm = get_llm_client()
        self._load_prompt()

    def _load_prompt(self):
        """加载提示词模板"""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"提示词文件不存在: {self.PROMPT_PATH}")
        self._prompt = self.PROMPT_PATH.read_text(encoding='utf-8')

    def summarize(self, aggregated_commits: List[Dict], project_config: Dict) -> ProjectSummary:
        """生成项目摘要

        Args:
            aggregated_commits: 聚合后的 commit 列表（已分类）
            project_config: 项目配置

        Returns:
            ProjectSummary
        """
        logger = logging.getLogger(__name__)

        context = self._build_context(aggregated_commits, project_config)
        logger.info(f">>> [项目总结] 项目: {project_config['name']}")
        logger.info(f">>> [项目总结] 输入: {len(aggregated_commits)} 个聚合组")

        try:
            response = self.llm.generate(self._prompt.format(context=context))
            summary = self._parse_summary(response, project_config["id"])
            logger.info(f">>> [项目总结] 完成: {summary.technical_highlights[:50]}...")
            return summary
        except Exception as e:
            logger.warning(f"项目总结失败: {e}，使用降级策略")
            return self._fallback_summary(aggregated_commits, project_config)

    def _build_context(self, commits: List[Dict], project_config: Dict) -> str:
        """构建 LLM 输入（压缩格式）"""
        parts = [
            f"项目: {project_config['name']}",
            f"技术栈: {', '.join(project_config.get('tech_stack', []))}",
            f"总提交数: {sum(c.get('task_count', 0) for c in commits)}",
        ]

        # 按类型分组统计
        by_type = {}
        for commit in commits:
            ctype = commit.get("type", "other")
            if ctype not in by_type:
                by_type[ctype] = []
            by_type[ctype].append(commit)

        for ctype, items in by_type.items():
            parts.append(f"\n## {ctype.upper()} ({len(items)} 组)")
            # 每类只取代表性的 5-10 条
            for item in items[:5]:
                tasks = item.get('tasks', [])[:3]  # 每组最多 3 个任务
                for task in tasks:
                    parts.append(f"  - {task[:60]}")

        return "\n".join(parts)

    def _parse_summary(self, response: str, project_id: str) -> ProjectSummary:
        """解析 LLM 响应"""
        try:
            # 尝试解析 JSON
            data = json.loads(response)
            return ProjectSummary(
                project_id=project_id,
                technical_highlights=data.get("technical_highlights", ""),
                key_achievements=data.get("key_achievements", []),
                main_contributions=data.get("main_contributions", [])
            )
        except json.JSONDecodeError:
            # 降级：解析文本格式
            return self._parse_text_summary(response, project_id)

    def _parse_text_summary(self, response: str, project_id: str) -> ProjectSummary:
        """解析文本格式响应"""
        lines = response.split('\n')
        technical_highlights = ""
        key_achievements = []
        main_contributions = []

        current_section = None
        for line in lines:
            line = line.strip()
            if "技术亮点" in line or "technical_highlights" in line:
                current_section = "highlights"
            elif "关键成果" in line or "key_achievements" in line:
                current_section = "achievements"
            elif "主要贡献" in line or "main_contributions" in line:
                current_section = "contributions"
            elif line.startswith(('- ', '• ', '* ')):
                content = line[2:].strip()
                if current_section == "achievements":
                    key_achievements.append(content)
                elif current_section == "contributions":
                    main_contributions.append(content)
            elif line and not line.startswith('#') and current_section == "highlights":
                technical_highlights += line + " "

        return ProjectSummary(
            project_id=project_id,
            technical_highlights=technical_highlights.strip() or "技术亮点待补充",
            key_achievements=key_achievements or ["关键成果待补充"],
            main_contributions=main_contributions or ["主要贡献待补充"]
        )

    def _fallback_summary(self, commits: List[Dict], project_config: Dict) -> ProjectSummary:
        """降级策略：基于规则生成摘要"""
        # 统计类型分布
        type_counts = {}
        for commit in commits:
            ctype = commit.get("type", "other")
            type_counts[ctype] = type_counts.get(ctype, 0) + commit.get('task_count', 0)

        # 技术亮点
        tech_highlights = f"使用 {', '.join(project_config.get('tech_stack', ['相关技术']))} 开发"

        # 关键成果
        achievements = []
        for ctype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:3]:
            achievements.append(f"完成 {count} 个 {ctype} 类任务")

        # 主要贡献
        contributions = [f"参与 {project_config['name']} 项目开发"]

        return ProjectSummary(
            project_id=project_config["id"],
            technical_highlights=tech_highlights,
            key_achievements=achievements,
            main_contributions=contributions
        )
