"""SuperAgent - 规则判断（被 graph.py 节点直接调用）"""
from ..agents.base import BaseAgent
from ..validators.output import OutputValidator


class SuperAgent(BaseAgent):
    """Super Agent - 纯规则判断"""

    def __init__(self, max_iteration: int = 3):
        super().__init__("super_agent")
        self.max_iteration = max_iteration
        self.validator = OutputValidator()

    def _rule_check(self, content: str, mode: str, iteration: int):
        """规则层快速判断"""
        if iteration >= self.max_iteration:
            return "stop", f"max_iterations_reached ({iteration}/{self.max_iteration})", content

        if not content:
            return "generate", "no_content_yet", None

        validation = self.validator.validate(content, mode)

        if validation.is_valid:
            return "stop", "validation_passed", content

        if validation.errors:
            if iteration < self.max_iteration:
                return "generate", f"validation_failed: {validation.errors[0]}", None
            else:
                return "stop", f"max_iterations_with_errors: {validation.errors}", content

        return "stop", f"passed_with_warnings: {validation.warnings}", content
