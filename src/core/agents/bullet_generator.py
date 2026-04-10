"""Bullet 生成 Agent - 基于项目摘要生成简历 bullets"""
from pathlib import Path
from typing import List, Optional
import logging

from src.core.llm.client import get_llm_client
from .project_summarizer import ProjectSummary


class BulletGeneratorAgent:
    """基于项目摘要生成简历 bullet points

    输入:
    - 项目摘要（技术亮点、成果、贡献）
    - claude.md（项目规范）
    - README（项目说明）

    输出:
    - 3-5 条简历 bullet points
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "resume" / "bullet_generator.txt"

    def __init__(self):
        self.llm = get_llm_client()
        self._load_prompt()

    def _load_prompt(self):
        """加载提示词模板"""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"提示词文件不存在: {self.PROMPT_PATH}")
        self._prompt = self.PROMPT_PATH.read_text(encoding='utf-8')

    def generate(
        self,
        summary: ProjectSummary,
        claude_md: Optional[str] = None,
        readme: Optional[str] = None
    ) -> List[str]:
        """生成 bullet points

        Args:
            summary: 项目摘要
            claude_md: 项目规范文件（可选）
            readme: 项目说明文档（可选）

        Returns:
            bullet points 列表
        """
        logger = logging.getLogger(__name__)

        context = self._build_context(summary, claude_md, readme)
        logger.info(f">>> [Bullet 生成] 项目: {summary.project_id}")

        try:
            response = self.llm.generate(self._prompt.format(context=context))
            bullets = self._parse_bullets(response)
            logger.info(f">>> [Bullet 生成] 完成: {len(bullets)} 条")
            return bullets
        except Exception as e:
            logger.warning(f"Bullet 生成失败: {e}，使用降级策略")
            return self._fallback_bullets(summary)

    def _build_context(self, summary: ProjectSummary, claude_md: Optional[str], readme: Optional[str]) -> str:
        """构建 LLM 输入"""
        parts = [
            "## 项目摘要",
            f"**技术亮点**: {summary.technical_highlights}",
            f"**关键成果**:",
        ]
        for achievement in summary.key_achievements:
            parts.append(f"  - {achievement}")

        parts.append("\n**主要贡献**:")
        for contribution in summary.main_contributions:
            parts.append(f"  - {contribution}")

        if claude_md:
            parts.append("\n## 项目规范 (CLAUDE.md)")
            parts.append(claude_md[:800])  # 限制长度

        if readme:
            parts.append("\n## 项目说明 (README)")
            parts.append(readme[:800])

        return "\n".join(parts)

    def _parse_bullets(self, response: str) -> List[str]:
        """解析 bullet points"""
        bullets = []
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith(('- ', '• ', '* ')):
                bullets.append(line[2:].strip())
            elif line and line[0].isdigit() and line[1] in '.)、':
                bullets.append(line[2:].strip())
        return bullets if bullets else []

    def _fallback_bullets(self, summary: ProjectSummary) -> List[str]:
        """降级策略：基于规则生成 bullets"""
        bullets = []

        # 从关键成果转换
        for achievement in summary.key_achievements[:3]:
            bullets.append(achievement)

        # 从技术亮点转换
        if summary.technical_highlights:
            bullets.append(summary.technical_highlights[:50])

        return bullets[:5] if bullets else ["参与项目开发，完成相关任务"]
