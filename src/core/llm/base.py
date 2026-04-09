"""LLM 客户端基类"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    @abstractmethod
    def generate(self, user_prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """生成文本

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（temperature, max_tokens等）

        Returns:
            生成的文本
        """
        pass
