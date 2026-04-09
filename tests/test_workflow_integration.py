"""测试工作流集成"""
import unittest
import sys
from pathlib import Path

# 添加 src 到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.core.workflow.state import WorkflowState
from src.core.validators.output import OutputValidator


class TestWorkflowComponents(unittest.TestCase):
    """测试工作流组件"""

    def test_workflow_state_with_mode(self):
        """测试带模式的状态"""
        state = WorkflowState()
        state.add_message("user", "测试输入")

        self.assertEqual(state.input_text, "测试输入")

    def test_validator_with_modes(self):
        """测试不同模式的校验"""
        validator = OutputValidator()

        # 简约模式 - 要求较宽松
        simple_result = validator.validate(
            "这是一段简单的周报内容，用于测试简约模式的校验功能。",
            "simple"
        )
        self.assertTrue(simple_result.is_valid)

        # 专业模式 - 需要结构
        professional_result = validator.validate(
            "这是一段没有结构的专业模式内容。",
            "professional"
        )
        # 应该有警告但可能通过（因为长度足够）
        self.assertTrue(len(professional_result.warnings) > 0 or not professional_result.is_valid)


class TestGitReportSource(unittest.TestCase):
    """测试 Git 周报内容源"""

    def test_get_metadata(self):
        """测试获取元数据"""
        from src.integrations.git_report.source import GitReportSource
        source = GitReportSource()
        metadata = source.get_metadata()

        self.assertEqual(metadata["source_type"], "git_commits")
        self.assertIn("author", metadata)
        self.assertEqual(metadata["supported_formats"], ["json"])


if __name__ == '__main__':
    unittest.main()
