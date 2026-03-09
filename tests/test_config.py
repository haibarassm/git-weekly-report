"""配置模块测试"""
import unittest
import json
from pathlib import Path
import tempfile
import shutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config


class TestConfig(unittest.TestCase):
    """配置测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """测试后清理"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_get_llm_config(self):
        """测试获取LLM配置"""
        config_data = {
            "llm": {
                "provider": "ollama",
                "model": "qwen2.5:14b",
                "api_base": "http://localhost:11434",
                "temperature": 0.7
            },
            "output_dir": "/app/output",
            "author": "Test User"
        }

        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = Config(str(config_file))
        llm_config = config.get_llm_config()

        self.assertEqual(llm_config["provider"], "ollama")
        self.assertEqual(llm_config["model"], "qwen2.5:14b")
        self.assertEqual(llm_config["temperature"], 0.7)

    def test_get_author(self):
        """测试获取作者配置"""
        config_data = {
            "author": "Test User <test@example.com>",
            "llm": {},
            "output_dir": "/app/output"
        }

        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = Config(str(config_file))
        author = config.get_author()

        self.assertEqual(author, "Test User <test@example.com>")

    def test_get_output_dir(self):
        """测试获取输出目录"""
        config_data = {
            "llm": {},
            "output_dir": "/test/output"
        }

        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = Config(str(config_file))
        output_dir = config.get_output_dir()

        self.assertEqual(str(output_dir), "/test/output")

    def test_config_file_not_found(self):
        """测试配置文件不存在"""
        with self.assertRaises(FileNotFoundError) as context:
            Config("/non/existent/config.json")

        self.assertIn("配置文件不存在", str(context.exception))

    def test_default_values(self):
        """测试默认值"""
        config_data = {}
        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = Config(str(config_file))

        # 测试默认值
        self.assertEqual(config.get_author(), "")
        self.assertEqual(config.get_llm_config(), {})


if __name__ == '__main__':
    unittest.main()
