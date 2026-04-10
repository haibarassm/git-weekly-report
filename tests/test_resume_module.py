"""测试简历生成模块"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from src.integrations.resume.config_loader import ConfigLoader
from src.integrations.resume.document_builder import DocumentBuilder


class TestConfigLoader:
    """测试配置加载器"""

    def test_load_empty_config(self, tmp_path):
        """测试加载空配置"""
        config_path = tmp_path / "projects.json"
        loader = ConfigLoader(str(config_path))
        data = loader.load_config()
        assert data == {"projects": []}

    def test_save_and_load_config(self, tmp_path):
        """测试保存和加载配置"""
        config_path = tmp_path / "projects.json"
        loader = ConfigLoader(str(config_path))

        test_data = {
            "projects": [
                {
                    "id": "test-project",
                    "name": "测试项目",
                    "sources": [{"path": "/path/to/repo", "branch": "main"}],
                    "tech_stack": ["Python", "Go"],
                    "highlights": ["测试亮点"],
                    "notes": "测试备注"
                }
            ]
        }

        loader.save_config(test_data)
        loaded = loader.load_config()

        assert loaded == test_data

    def test_get_projects(self, tmp_path):
        """测试获取项目列表"""
        config_path = tmp_path / "projects.json"
        loader = ConfigLoader(str(config_path))

        test_data = {
            "projects": [
                {"id": "p1", "name": "项目1"},
                {"id": "p2", "name": "项目2"},
            ]
        }
        loader.save_config(test_data)

        projects = loader.get_projects()
        assert len(projects) == 2
        assert projects[0]["id"] == "p1"

    def test_add_project(self, tmp_path):
        """测试添加项目"""
        config_path = tmp_path / "projects.json"
        loader = ConfigLoader(str(config_path))

        project = {
            "id": "new-project",
            "name": "新项目",
            "sources": [],
            "tech_stack": [],
            "highlights": [],
            "notes": ""
        }

        result = loader.add_project(project)
        assert result is True

        projects = loader.get_projects()
        assert len(projects) == 1
        assert projects[0]["id"] == "new-project"

    def test_delete_project(self, tmp_path):
        """测试删除项目"""
        config_path = tmp_path / "projects.json"
        loader = ConfigLoader(str(config_path))

        test_data = {
            "projects": [
                {"id": "p1", "name": "项目1"},
                {"id": "p2", "name": "项目2"},
            ]
        }
        loader.save_config(test_data)

        result = loader.delete_project("p1")
        assert result is True

        projects = loader.get_projects()
        assert len(projects) == 1
        assert projects[0]["id"] == "p2"


class TestDocumentBuilder:
    """测试文档构建器"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        config = Mock()
        config.get_author.return_value = "Test User"
        config.get_output_dir.return_value = str(Path(__file__).parent / "test_output")
        return config

    @pytest.fixture
    def sample_resume_projects(self):
        """示例简历项目"""
        return [
            {
                "name": "测试项目",
                "tech_stack": "Python, LangGraph",
                "bullets": [
                    "Built 周报生成系统 using LangGraph",
                    "Designed 多 Agent 工作流架构",
                    "Implemented Gradio Web 界面"
                ],
                "highlights": ["独立项目", "从 0 到 1"]
            }
        ]

    def test_build_document(self, mock_config, sample_resume_projects, tmp_path):
        """测试构建 Word 文档"""
        # 修改输出目录到临时目录
        mock_config.get_output_dir.return_value = str(tmp_path)

        builder = DocumentBuilder(mock_config)
        filepath = builder.build(sample_resume_projects)

        assert filepath.exists()
        assert filepath.suffix == ".docx"
        assert "resume" in filepath.name


@pytest.fixture
def sample_projects_json(tmp_path):
    """创建示例项目配置文件"""
    config_file = tmp_path / "projects.json"
    test_data = {
        "projects": [
            {
                "id": "test-project",
                "name": "测试项目",
                "description": "项目描述",
                "sources": [
                    {"path": "/path/to/repo", "branch": "main"}
                ],
                "tech_stack": ["Python", "Go"],
                "highlights": ["项目亮点"],
                "notes": "备注"
            }
        ]
    }

    import json
    config_file.write_text(json.dumps(test_data, ensure_ascii=False), encoding='utf-8')
    return str(config_file)
