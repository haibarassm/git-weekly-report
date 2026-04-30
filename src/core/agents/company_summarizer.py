"""公司经历总结 Agent - 从项目中提取公司工作经历"""
from pathlib import Path
from typing import List, Dict
import logging
import json

from src.core.llm.client import get_llm_client


class CompanySummarizerAgent:
    """公司经历总结 Agent

    输入：
    - 公司信息（名称、行业、职位）
    - 该公司的多个项目信息（项目名称、主要贡献、关键成果）

    输出：
    - 公司工作经历（主要职责，从项目中提取和整合）
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "company" / "work_experience_generator.txt"

    def __init__(self):
        self.llm = get_llm_client()
        self._load_prompt()

    def _load_prompt(self):
        """加载提示词模板"""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"提示词文件不存在: {self.PROMPT_PATH}")
        self._prompt = self.PROMPT_PATH.read_text(encoding='utf-8')

    def generate_work_experience(
        self,
        company_info: Dict,
        projects: List[Dict]
    ) -> str:
        """生成公司工作经历

        Args:
            company_info: 公司信息 {id, name, industry, position}
            projects: 该公司的项目列表 [{name, main_contributions, key_achievements, ...}]

        Returns:
            工作经历描述（主要职责，多行文本）
        """
        logger = logging.getLogger(__name__)

        context = self._build_context(company_info, projects)
        logger.info(f">>> [公司经历] 公司: {company_info['name']}, 项目数: {len(projects)}")

        try:
            prompt = self._prompt.replace("{context}", context)
            response = self.llm.generate(prompt)
            work_experience = self._parse_response(response)

            # 如果 LLM 生成的内容为空，使用 fallback 策略
            if not work_experience or len(work_experience.strip()) == 0:
                logger.warning(f">>> [公司经历] LLM 生成内容为空，使用 fallback 策略")
                return self._fallback_work_experience(company_info, projects)

            logger.info(f">>> [公司经历] 生成完成: {len(work_experience)} 字符")
            return work_experience
        except Exception as e:
            logger.warning(f"公司经历生成失败: {e}，使用降级策略")
            return self._fallback_work_experience(company_info, projects)

    def _build_context(self, company_info: Dict, projects: List[Dict]) -> str:
        """构建 LLM 输入"""
        parts = [
            f"**公司名称**: {company_info.get('name', '')}",
            f"**所属行业**: {company_info.get('industry', '')}",
            f"**职位**: {company_info.get('position', '')}",
            "",
            "## 项目列表",
        ]

        for idx, project in enumerate(projects, 1):
            parts.append(f"\n### {idx}. 【项目名称】{project.get('name', '')}")
            parts.append(f"**主要贡献（仅限此项目）**:")
            for contrib in project.get('main_contributions', []):
                # 明确标识这是哪个项目的模块
                parts.append(f"  - 【{project.get('name', '')}】{contrib}")

            if project.get('key_achievements'):
                parts.append(f"**关键成果（仅限此项目）**:")
                for achievement in project.get('key_achievements', []):
                    parts.append(f"  - 【{project.get('name', '')}】{achievement}")

        return "\n".join(parts)

    def _parse_response(self, response: str) -> str:
        """解析 LLM 响应"""
        logger = logging.getLogger(__name__)

        # 处理 LangChain 流式响应格式
        if response.strip().startswith('['):
            try:
                chunks = json.loads(response)
                response = ''.join(chunk.get('text', '') for chunk in chunks)
                logger.info(f"从 LangChain 格式提取文本")
            except json.JSONDecodeError:
                pass

        # 清理响应：移除 markdown 代码块标记
        cleaned = response.strip().replace('```', '').strip()

        # 过滤掉说明文字
        filter_keywords = [
            '主要职责：', '工作经历：', '输出：', '说明：', '示例：',
            '基于公司信息和项目列表', '生成以下', '根据以下', '基于公司提供的项目信息',
            '基于提供的公司信息', '以下是生成的', '以下是',
            '每行一条', '以 `● ` 开头', '不要添加其他说明', '我生成了以下',
            '## 任务', '## 输出格式', '## 注意事项', '## 要求', '## 使用',
            '## 严格要求', '## 输出', '## 注意'
        ]
        lines = []
        for line in cleaned.split('\n'):
            line = line.strip()
            if not line:
                continue
            # 跳过包含过滤关键词的行
            if any(keyword in line for keyword in filter_keywords):
                logger.info(f">>> [公司经历] 过滤说明文字: {line[:50]}")
                continue
            # 跳过纯英文行（通常是 prompt 说明）
            if line.isascii() and not any('●' in c or c in '，。、；：*'):
                logger.info(f">>> [公司经历] 过滤纯英文行: {line[:50]}")
                continue
            # 只保留以 ●、* 或 - 开头的行（主要职责描述）
            if line and not (line.startswith('●') or line.startswith('*') or line.startswith('-')):
                logger.info(f">>> [公司经历] 过滤非列表项的行: {line[:50]}")
                continue

            # 统一转换为 ● 格式
            if line.startswith('*'):
                line = '●' + line[1:].strip()
            elif line.startswith('-'):
                line = '●' + line[1:].strip()

            lines.append(line)

        result = '\n'.join(lines)
        logger.info(f"解析到工作经历: {len(result)} 字符")
        return result

    def _fallback_work_experience(self, company_info: Dict, projects: List[Dict]) -> str:
        """降级策略：基于规则生成工作经历"""
        responsibilities = []

        # 从所有项目的主要贡献中提取
        for project in projects:
            for contrib in project.get('main_contributions', []):
                # 简化描述，移除分类前缀
                simplified = contrib.split('：')[-1] if '：' in contrib else contrib
                responsibilities.append(f"● {simplified}")

        # 如果没有足够内容，添加通用描述
        if len(responsibilities) < 3:
            position = company_info.get('position', '开发工程师')
            responsibilities.append(f"● 负责{position}相关工作")
            responsibilities.append(f"● 参与项目需求分析、设计和开发")
            responsibilities.append(f"● 技术文档编写和代码维护")

        return '\n'.join(responsibilities[:8])  # 最多8条
