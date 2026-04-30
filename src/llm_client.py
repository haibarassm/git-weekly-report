"""LLM客户端模块 - 使用 LangChain 组件以支持 LangSmith 追踪"""
import os
import logging
from typing import Optional
from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('llm_client.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    """LLM客户端基类"""

    @abstractmethod
    def generate(self, user_prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        生成文本

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（temperature, max_tokens等）

        Returns:
            生成的文本
        """
        pass


class OllamaClient(BaseLLMClient):
    """Ollama客户端 - 使用 LangChain ChatOllama"""

    def __init__(self, base_url: str, model: str, timeout: int = 120):
        """
        初始化Ollama客户端

        Args:
            base_url: API地址
            model: 模型名称
            timeout: 超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        # 使用 LangChain 的 ChatOllama，自动支持 LangSmith 追踪
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.7,
            timeout=timeout,
        )
        logger.info(f"初始化Ollama客户端: {self.base_url}, 模型: {self.model}")

    def generate(self, user_prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        生成文本

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（temperature, max_tokens等）

        Returns:
            生成的文本
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=user_prompt))

        try:
            # LangChain 会自动追踪到 LangSmith
            response = self.llm.invoke(messages)
            logger.info(f"Ollama请求成功，返回 {len(response.content)} 字符")
            return response.content
        except Exception as e:
            error_msg = f"Ollama API请求失败: {str(e)}\n\n请确保：\n1. Ollama正在运行\n2. API地址配置正确\n3. 模型已下载（运行: ollama pull {self.model}）"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek客户端 - 使用 LangChain ChatOpenAI（兼容 OpenAI API）"""

    def __init__(
        self, api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat", timeout: int = 120
    ):
        """
        初始化DeepSeek客户端

        Args:
            api_key: API密钥
            base_url: API地址
            model: 模型名称
            timeout: 超时时间（秒）
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        # 使用 LangChain 的 ChatOpenAI，自动支持 LangSmith 追踪
        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
            timeout=timeout,
        )
        logger.info(f"初始化DeepSeek客户端: {self.base_url}, 模型: {self.model}")

    def generate(self, user_prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        生成文本

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（temperature, max_tokens等）

        Returns:
            生成的文本
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=user_prompt))

        try:
            # LangChain 会自动追踪到 LangSmith
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            error_msg = f"DeepSeek API请求失败: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


class OpenAIClient(BaseLLMClient):
    """OpenAI客户端 - 使用 LangChain ChatOpenAI"""

    def __init__(
        self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o", timeout: int = 120
    ):
        """
        初始化OpenAI客户端

        Args:
            api_key: API密钥
            base_url: API地址
            model: 模型名称
            timeout: 超时时间（秒）
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

        # 使用 LangChain 的 ChatOpenAI，自动支持 LangSmith 追踪
        self.llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
            timeout=timeout,
        )
        logger.info(f"初始化OpenAI客户端: {self.base_url}, 模型: {self.model}")

    def generate(self, user_prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        生成文本

        Args:
            user_prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            **kwargs: 额外参数（temperature, max_tokens等）

        Returns:
            生成的文本
        """
        messages = []

        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        messages.append(HumanMessage(content=user_prompt))

        try:
            # LangChain 会自动追踪到 LangSmith
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            error_msg = f"OpenAI API请求失败: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


def create_llm_client(config: dict) -> BaseLLMClient:
    """
    根据配置创建LLM客户端

    Args:
        config: LLM配置字典

    Returns:
        LLM客户端实例
    """
    provider = config.get("provider", "ollama").lower()

    if provider == "ollama":
        return OllamaClient(
            base_url=config.get("api_base", "http://localhost:11434"),
            model=config.get("model", "llama3.1:8b"),
            timeout=config.get("timeout", 120),
        )
    elif provider == "deepseek":
        return DeepSeekClient(
            api_key=config.get("api_key", ""),
            base_url=config.get("api_base", "https://api.deepseek.com"),
            model=config.get("model", "deepseek-chat"),
            timeout=config.get("timeout", 120),
        )
    elif provider == "openai":
        return OpenAIClient(
            api_key=config.get("api_key", ""),
            base_url=config.get("api_base", "https://api.openai.com/v1"),
            model=config.get("model", "gpt-4o"),
            timeout=config.get("timeout", 120),
        )
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}")
