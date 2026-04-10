"""配置管理模块"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class Config:
    """配置管理类 - 支持环境变量覆盖"""

    # 默认配置路径
    DEFAULT_NAPS_CONFIG = "config/naps.json"
    DEFAULT_PROJECTS_CONFIG = "config/projects.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径（可选）
                        - 环境变量 NAPS_CONFIG_PATH 优先
                        - 其次是传入的 config_path
                        - 最后是默认路径 config/naps.json
        """
        # 确定配置文件路径
        if config_path is None:
            config_path = os.getenv("NAPS_CONFIG_PATH", self.DEFAULT_NAPS_CONFIG)

        # 支持通过 NAPS_CONFIG_DIR 批量设置
        config_dir = os.getenv("NAPS_CONFIG_DIR")
        if config_dir:
            config_path = f"{config_dir}/naps.json"

        # 如果是相对路径，相对于项目根目录
        path = Path(config_path)
        if not path.is_absolute():
            project_root = Path(__file__).parent.parent
            path = project_root / config_path

        self.config_path = path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self._config.get("llm", {})

    def get_output_dir(self) -> str:
        """获取输出目录"""
        output_dir = self._config.get("output_dir", "./output")
        return str(output_dir)

    def get_base_dir(self) -> str:
        """获取项目基础目录"""
        return self._config.get("base_dir", ".")

    @property
    def base_dir(self) -> str:
        return self.get_base_dir()

    def get_author(self) -> str:
        """获取作者信息（用于筛选提交记录）"""
        return self._config.get("author", "")

    def get_langsmith_config(self) -> Dict[str, Any]:
        """获取 LangSmith 配置（用于 LangChain 可观测性）"""
        langsmith_config = self._config.get("langsmith", {})

        # 从环境变量获取配置（如果存在）
        env_config = {
            "enabled": os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
            "api_key": os.getenv("LANGCHAIN_API_KEY", ""),
            "project": os.getenv("LANGCHAIN_PROJECT", langsmith_config.get("project", "naps-report-generator")),
            "endpoint": os.getenv("LANGCHAIN_ENDPOINT", langsmith_config.get("endpoint", "https://api.smith.langchain.com")),
        }

        # 合并配置文件和环境变量
        return {
            "enabled": langsmith_config.get("enabled", False) or env_config["enabled"],
            "api_key": langsmith_config.get("api_key", "") or env_config["api_key"],
            "project": env_config["project"],
            "endpoint": env_config["endpoint"],
        }


# 全局配置实例
config = Config()
