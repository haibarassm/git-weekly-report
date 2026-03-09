"""配置管理模块"""
import json
import os
from pathlib import Path
from typing import Any, Dict


class Config:
    """配置管理类"""

    def __init__(self, config_path: str = None):
        """
        初始化配置

        Args:
            config_path: 配置文件路径，默认为项目根目录下的config.json
        """
        if config_path is None:
            # 默认配置文件路径
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config.json"

        self.config_path = Path(config_path)
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

    def get_output_dir(self) -> Path:
        """获取输出目录"""
        output_dir = self._config.get("output_dir", "./output")
        return Path(output_dir)

    def get_author(self) -> str:
        """获取作者信息（用于筛选提交记录）"""
        return self._config.get("author", "")


# 全局配置实例
config = Config()
