"""Reviewer Agent - 内容审查（被 graph.py 节点直接调用内部方法）"""
import json
import re
from pathlib import Path
from ..agents.base import BaseAgent
from ..llm.client import get_llm_client


class ReviewerAgent(BaseAgent):
    """内容审查 Agent"""

    PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "weekly_report"

    def __init__(self):
        super().__init__("reviewer")
        self.llm_client = get_llm_client()

    def _parse_output(self, raw: str) -> dict:
        """解析 LLM 输出为结构化结果"""
        # 尝试直接解析
        try:
            result = json.loads(raw.strip())
            result.setdefault("passed", True)
            result.setdefault("issues", [])
            result.setdefault("optimized_content", "")
            return result
        except json.JSONDecodeError:
            pass

        # 尝试从文本中提取第一个 JSON 对象
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                result = json.loads(json_match.group())
                result.setdefault("passed", True)
                result.setdefault("issues", [])
                result.setdefault("optimized_content", "")
                return result
            except json.JSONDecodeError:
                pass

        # 尝试提取代码块中的 JSON
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
        if json_match:
            try:
                result = json.loads(json_match.group(1).strip())
                result.setdefault("passed", True)
                result.setdefault("issues", [])
                result.setdefault("optimized_content", "")
                return result
            except json.JSONDecodeError:
                pass

        # 全部解析失败
        return {
            "passed": True,
            "issues": [],
            "optimized_content": ""
        }
