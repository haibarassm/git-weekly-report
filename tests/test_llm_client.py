"""LLM客户端测试"""
import unittest
from unittest.mock import Mock, patch
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm_client import OllamaClient, DeepSeekClient, OpenAIClient


class TestOllamaClient(unittest.TestCase):
    """Ollama客户端测试"""

    def setUp(self):
        """测试前准备"""
        self.client = OllamaClient(
            base_url="http://localhost:11434",
            model="qwen2.5:14b",
            timeout=30
        )

    @patch('src.llm_client.requests.post')
    def test_generate_success(self, mock_post):
        """测试成功生成"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "生成的报告内容"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.client.generate(
            user_prompt="测试提示",
            system_prompt="系统提示"
        )

        self.assertEqual(result, "生成的报告内容")
        mock_post.assert_called_once()

    @patch('src.llm_client.requests.post')
    def test_generate_with_system_prompt(self, mock_post):
        """测试带系统提示词的生成"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "生成的报告"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        self.client.generate(
            user_prompt="用户提示",
            system_prompt="系统提示"
        )

        call_args = mock_post.call_args
        messages = call_args[1]['json']['messages']
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['role'], 'system')
        self.assertEqual(messages[1]['role'], 'user')

    @patch('src.llm_client.requests.post')
    def test_generate_request_error(self, mock_post):
        """测试请求错误"""
        mock_post.side_effect = requests.RequestException("连接失败")

        with self.assertRaises(RuntimeError) as context:
            self.client.generate(user_prompt="测试")

        self.assertIn("Ollama API请求失败", str(context.exception))


class TestDeepSeekClient(unittest.TestCase):
    """DeepSeek客户端测试"""

    def setUp(self):
        """测试前准备"""
        self.client = DeepSeekClient(
            api_key="test_key",
            model="deepseek-chat"
        )

    @patch('src.llm_client.requests.post')
    def test_generate_success(self, mock_post):
        """测试成功生成"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "DeepSeek生成的报告"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.client.generate(
            user_prompt="测试提示",
            system_prompt="系统提示"
        )

        self.assertEqual(result, "DeepSeek生成的报告")


class TestOpenAIClient(unittest.TestCase):
    """OpenAI客户端测试"""

    def setUp(self):
        """测试前准备"""
        self.client = OpenAIClient(
            api_key="test_key",
            model="gpt-4o"
        )

    @patch('src.llm_client.requests.post')
    def test_generate_success(self, mock_post):
        """测试成功生成"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "OpenAI生成的报告"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.client.generate(
            user_prompt="测试提示",
            system_prompt="系统提示"
        )

        self.assertEqual(result, "OpenAI生成的报告")


if __name__ == '__main__':
    unittest.main()
