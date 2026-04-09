"""测试核心框架 - 标准化接口版本"""
import unittest
import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.core.workflow.state import WorkflowState
from src.core.validators.output import OutputValidator


class TestWorkflowState(unittest.TestCase):
    """测试 WorkflowState"""

    def test_state_initialization(self):
        """测试状态初始化"""
        state = WorkflowState()
        self.assertEqual(state.messages, [])
        self.assertEqual(state.input_text, "")
        self.assertEqual(state.iteration, 0)

    def test_add_message(self):
        """测试添加消息"""
        state = WorkflowState()
        state.add_message("user", "test input")

        self.assertEqual(len(state.messages), 1)
        self.assertEqual(state.input_text, "test input")

    def test_iteration_count(self):
        """测试迭代计数"""
        state = WorkflowState()
        state.add_message("user", "input")
        state.add_message("generator", "draft1")
        state.add_message("reviewer", "review1")
        state.add_message("generator", "draft2")

        self.assertEqual(state.iteration, 2)

    def test_current_draft(self):
        """测试获取当前草稿"""
        state = WorkflowState()
        state.add_message("user", "input")
        state.add_message("generator", "draft 1")
        state.add_message("generator", "draft 2")

        self.assertEqual(state.current_draft, "draft 2")

    def test_reviewed_text(self):
        """测试获取审查结果"""
        state = WorkflowState()
        state.add_message("user", "input")
        state.add_message("generator", "draft")
        state.add_message("reviewer", "reviewed")

        self.assertEqual(state.reviewed_text, "reviewed")


class TestOutputValidator(unittest.TestCase):
    """测试 OutputValidator"""

    def setUp(self):
        self.validator = OutputValidator()

    def test_empty_content(self):
        """测试空内容"""
        result = self.validator.validate("", "simple")
        self.assertFalse(result.is_valid)
        self.assertIn("输出为空", result.errors)

    def test_too_short(self):
        """测试过短内容"""
        result = self.validator.validate("abc", "simple")
        self.assertFalse(result.is_valid)
        self.assertTrue(any("过短" in e for e in result.errors))

    def test_valid_simple_content(self):
        """测试有效的简约模式内容"""
        content = "这是一段测试内容，用于验证简约模式的输出校验功能是否正常工作。"
        result = self.validator.validate(content, "simple")
        self.assertTrue(result.is_valid)

    def test_valid_professional_content(self):
        """测试有效的专业模式内容"""
        content = """# 工作总结

1. 完成了系统重构工作
2. 优化了性能问题

整体进展顺利。"""
        result = self.validator.validate(content, "professional")
        self.assertTrue(result.is_valid)

    def test_professional_mode_structure_warning(self):
        """测试专业模式结构警告"""
        # 使用足够长度但没有结构的内容
        content = "这是一段没有结构的内容用于测试专业模式的结构检查。虽然长度足够了但是它没有分段也没有列表所以应该会有结构相关的警告提示用户使用更清晰的结构来组织内容。"
        result = self.validator.validate(content, "professional")
        # 内容足够长所以应该通过基本校验
        self.assertTrue(result.is_valid)
        # 但应该有结构相关的警告
        self.assertTrue(len(result.warnings) > 0)



if __name__ == '__main__':
    unittest.main()
