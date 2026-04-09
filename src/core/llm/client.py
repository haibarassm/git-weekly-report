"""LLM 客户端管理"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm_client import OllamaClient, DeepSeekClient, OpenAIClient
from config import config


# 客户端实例缓存
_client_cache = {}


def _is_docker() -> bool:
    """检测是否运行在 Docker 容器中"""
    return os.path.exists('/.dockerenv')


def _get_api_base(config_base: str) -> str:
    """根据运行环境自动调整 API 地址

    Docker 容器内：localhost → host.docker.internal
    本地运行：保持原样
    """
    if _is_docker() and 'localhost' in config_base:
        return config_base.replace('localhost', 'host.docker.internal')
    return config_base


def get_llm_client() -> 'BaseLLMClient':
    """获取配置的 LLM 客户端实例（单例）

    Returns:
        LLM 客户端实例
    """
    global _client_cache

    # 如果已有缓存，直接返回
    if 'default' in _client_cache:
        return _client_cache['default']

    # 创建新实例
    llm_config = config.get_llm_config()
    provider = llm_config.get('provider', 'ollama')

    if provider == 'ollama':
        api_base = _get_api_base(llm_config.get('api_base', 'http://localhost:11434'))
        client = OllamaClient(
            base_url=api_base,
            model=llm_config.get('model', 'qwen2.5:14b'),
            timeout=llm_config.get('timeout', 120)
        )
    elif provider == 'deepseek':
        client = DeepSeekClient(
            api_key=llm_config.get('api_key'),
            model=llm_config.get('model', 'deepseek-chat')
        )
    elif provider == 'openai':
        client = OpenAIClient(
            api_key=llm_config.get('api_key'),
            base_url=llm_config.get('base_url'),
            model=llm_config.get('model', 'gpt-4')
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    _client_cache['default'] = client
    return client


def reset_client_cache():
    """重置客户端缓存（用于测试或配置变更）"""
    global _client_cache
    _client_cache.clear()
