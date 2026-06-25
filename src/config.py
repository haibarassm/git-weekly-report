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

    def get_project_dirs(self) -> list:
        """获取所有项目目录列表（支持多目录扫描）"""
        # 如果配置了 project_dirs，直接使用
        project_dirs = self._config.get("project_dirs", [])
        if project_dirs:
            return project_dirs

        # 否则使用 base_dir
        base_dir = self.get_base_dir()
        if base_dir and base_dir != ".":
            # 自动添加常见的子目录
            dirs = [base_dir]
            base_path = Path(base_dir)

            # 检查常见的子目录
            common_subdirs = ["project", "projects", "极客时间"]
            for subdir in common_subdirs:
                subdir_path = base_path / subdir
                if subdir_path.exists():
                    dirs.append(str(subdir_path))

            return dirs

        return ["."]

    def to_container_path(self, host_path: str) -> str:
        """容器内把宿主机项目路径转成挂载路径（本地原样返回）。

        Docker 把宿主项目目录（如 C:\\\\Users\\\\sherry\\\\project）挂到 /app/project，
        而 projects.json 里的 source 路径是宿主绝对路径，需转成容器路径才读得到仓库。
        本地运行（无 PROJECT_BASE_DIR 环境变量）时直接原样返回。
        """
        import os
        container_base = os.getenv("PROJECT_BASE_DIR")
        if not container_base or not host_path:
            return host_path

        p = str(host_path).replace("\\", "/")
        for host_dir in self.get_project_dirs() or []:
            h = str(host_dir).replace("\\", "/")
            if p.lower().startswith(h.lower()):
                rel = p[len(h):].lstrip("/")
                return str(Path(container_base) / rel) if rel else container_base
        return host_path

    @property
    def base_dir(self) -> str:
        return self.get_base_dir()

    def get_author(self) -> str:
        """获取作者信息（用于筛选提交记录）"""
        return self._config.get("author", "")

    def get_author_by_platform(self, platform: str) -> str:
        """根据 Git 平台获取对应的作者信息"""
        platform = platform.lower()
        platform_key = f"{platform}_author"
        return self._config.get(platform_key, "")

    def get_authors(self) -> list:
        """获取所有作者列表（支持多邮箱/用户名）"""
        author = self._config.get("author", "")
        if not author:
            return []

        # 支持多种格式：
        # 1. 逗号分隔： "user1@example.com, user2@gmail.com"
        # 2. authors 数组
        authors_config = self._config.get("authors", [])
        if authors_config:
            return authors_config

        # 从 author 字段解析（支持逗号或分号分隔）
        import re
        # 匹配邮箱格式
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', author)
        if emails:
            return emails

        # 如果没有邮箱，按分隔符分割
        for sep in [',', ';', '，', '；']:
            if sep in author:
                return [a.strip() for a in author.split(sep) if a.strip()]

        # 单个作者
        return [author] if author else []

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
