"""Agent 基类"""
from ..workflow.state import WorkflowState


class BaseAgent:
    """Agent 基类"""

    def __init__(self, name: str):
        self.name = name
