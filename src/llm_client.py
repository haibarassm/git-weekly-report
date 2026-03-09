"""LLM客户端模块"""
import os
import requests
import logging
from typing import Optional
from abc import ABC, abstractmethod

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
    """Ollama客户端"""

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
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 4000),
            "temperature": kwargs.get("temperature", 0.7),
            "stream": False
        }

        logger.info(f"发送请求到Ollama: {self.base_url}/v1/chat/completions")
        logger.info(f"使用模型: {self.model}")

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            response_data = response.json()
            result = response_data["choices"][0]["message"]["content"]
            logger.info("Ollama请求成功")
            return result
        except requests.exceptions.Timeout:
            error_msg = f"Ollama API请求超时（{self.timeout}秒）。请检查模型是否已下载，或增加config.json中的timeout值。"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"无法连接到Ollama服务（{self.base_url}）。\n\n请确保：\n1. Ollama正在运行\n2. API地址配置正确\n3. 模型已下载（运行: ollama pull {self.model}）"
            logger.error(f"{error_msg}\n详细错误: {e}")
            raise RuntimeError(error_msg)
        except requests.RequestException as e:
            error_msg = f"Ollama API请求失败: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except (KeyError, IndexError) as e:
            error_msg = f"Ollama响应格式错误，请检查模型版本是否支持"
            logger.error(f"{error_msg}\n详细错误: {e}")
            raise RuntimeError(error_msg)


class DeepSeekClient(BaseLLMClient):
    """DeepSeek客户端（兼容OpenAI API）"""

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
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            raise RuntimeError(f"DeepSeek API请求失败: {e}")


class OpenAIClient(BaseLLMClient):
    """OpenAI客户端"""

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
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            raise RuntimeError(f"OpenAI API请求失败: {e}")


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
