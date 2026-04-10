"""配置加载器 - 加载 projects.json"""
import json
from pathlib import Path
from typing import List, Dict, Optional


class ConfigLoader:
    """加载和管理项目配置"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: projects.json 路径（可选，默认使用环境变量或默认路径）
        """
        import os
        self.config_path = config_path or os.getenv(
            "NAPS_PROJECTS_PATH",
            "config/projects.json"
        )
        self._projects_data = None

    def load_config(self) -> Dict:
        """加载 projects.json"""
        if self._projects_data is None:
            path = Path(self.config_path)
            if not path.exists():
                # 首次使用，返回空配置
                self._projects_data = {"projects": []}
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    self._projects_data = json.load(f)
        return self._projects_data

    def save_config(self, data: Dict):
        """保存 projects.json"""
        path = Path(self.config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self._projects_data = data

    def get_projects(self) -> List[Dict]:
        """获取所有项目列表"""
        data = self.load_config()
        return data.get("projects", [])

    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """根据 ID 获取项目"""
        projects = self.get_projects()
        for project in projects:
            if project.get("id") == project_id:
                return project
        return None

    def add_project(self, project: Dict) -> bool:
        """添加项目"""
        data = self.load_config()
        # 检查 ID 是否已存在
        for p in data["projects"]:
            if p.get("id") == project.get("id"):
                return False
        data["projects"].append(project)
        self.save_config(data)
        return True

    def update_project(self, project_id: str, project: Dict) -> bool:
        """更新项目"""
        data = self.load_config()
        for i, p in enumerate(data["projects"]):
            if p.get("id") == project_id:
                data["projects"][i] = project
                self.save_config(data)
                return True
        return False

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        data = self.load_config()
        for i, p in enumerate(data["projects"]):
            if p.get("id") == project_id:
                data["projects"].pop(i)
                self.save_config(data)
                return True
        return False
