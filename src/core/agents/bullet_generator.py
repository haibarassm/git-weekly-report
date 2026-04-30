"""Bullet 生成 Agent - 基于项目摘要生成简历 bullets"""
from pathlib import Path
from typing import List, Optional
import logging
import json

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
            # 使用 replace 避免花括号冲突
            prompt = self._prompt.replace("{context}", context)
            response = self.llm.generate(prompt)
            bullets = self._parse_bullets(response)
            logger.info(f">>> [Bullet 生成] 完成: {len(bullets)} 条")
            return bullets
        except Exception as e:
            logger.warning(f"Bullet 生成失败: {e}，使用降级策略")
            return self._fallback_bullets(summary)

    def _build_context(self, summary: ProjectSummary, claude_md: Optional[str], readme: Optional[str]) -> str:
        """构建 LLM 输入"""
        parts = [
            f"**项目名称**: {summary.project_id}",
            "",
            "## 项目摘要",
            f"**技术亮点**: {summary.technical_highlights}",
            f"**关键成果**:",
        ]
        for achievement in summary.key_achievements:
            parts.append(f"  - {achievement}")

        parts.append("\n**主要贡献**:")
        for contribution in summary.main_contributions:
            parts.append(f"  - {contribution}")

        # 只在没有关键成果时才使用 claude.md 和 readme
        if not summary.key_achievements and claude_md:
            parts.append("\n## 项目规范 (CLAUDE.md)")
            # 限制长度，只保留核心部分
            claude_content = claude_md[:2000] if claude_md else ""
            parts.append(claude_content)

        if not summary.key_achievements and readme:
            parts.append("\n## 项目说明 (README)")
            readme_content = readme[:1000] if readme else ""
            parts.append(readme_content)

        return "\n".join(parts)

    def _parse_bullets(self, response: str) -> List[str]:
        """解析 bullet points"""
        logger = logging.getLogger(__name__)

        # 处理 LangChain 流式响应格式 [{"type":"text","text":"..."}]
        if response.strip().startswith('['):
            try:
                # 解析 JSON 数组
                chunks = json.loads(response)
                # 提取所有 text 字段
                full_text = ''.join(chunk.get('text', '') for chunk in chunks)
                response = full_text
                logger.info(f"从 LangChain 格式提取文本，长度: {len(response)}")
            except json.JSONDecodeError:
                pass  # 不是流式格式，继续处理

        bullets = []
        # 过滤关键词：包含这些词的行视为说明文字，不作为 bullet
        filter_keywords = [
            '要求', '输出格式', '示例', '注意事项', '反例', '正例',
            '不要', '提醒', '每行一条', '以 `- ` 开头',
            '具体任务', '高层次', '抽象', '列举', '任务名称',
            'REFACTOR', 'FEATURE', 'FIX'  # prompt 中的示例
        ]

        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue

            # 检查是否包含过滤关键词（说明文字）
            if any(keyword in line for keyword in filter_keywords):
                logger.info(f"过滤说明文字: {line[:50]}")
                continue

            # 检查是否是 prompt 的标题行（如 ## xxx）
            if line.startswith('##') or line.startswith('#'):
                logger.info(f"过滤标题行: {line[:50]}")
                continue

            # 解析 bullet
            if line.startswith(('- ', '• ', '* ', '-')):
                bullet = line[2:].strip() if line[1] in [' ', '*', '•'] else line[1:].strip()
                if bullet:
                    bullets.append(bullet)
            elif line and line[0].isdigit() and line[1] in '.)、':
                bullet = line[2:].strip()
                if bullet:
                    bullets.append(bullet)

        logger.info(f"解析到 {len(bullets)} 条 bullets")
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
