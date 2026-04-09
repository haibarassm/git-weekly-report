"""Generator Agent - 内容生成（被 graph.py 节点直接调用内部方法）"""
from pathlib import Path
from ..agents.base import BaseAgent
from ..llm.client import get_llm_client


class GeneratorAgent(BaseAgent):
    """内容生成 Agent"""

    PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

    def __init__(self):
        super().__init__("generator")
        self.llm_client = get_llm_client()

    def _read_prompt(self, filename: str) -> str:
        """读取 prompt 文件"""
        prompt_path = self.PROMPTS_DIR / filename
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 文件不存在: {prompt_path}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
