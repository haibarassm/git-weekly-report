"""工作流状态定义 - 轻量级设计，只存储消息历史

消息结构约定（标准 OpenAI 格式）：
- user:       {"role": "user", "content": "输入文本"}
- generator:  {"role": "generator", "content": "生成的文本"}
- reviewer:   {"role": "reviewer", "content": '{"passed": bool, "issues": [], "optimized_content": "..."}'}
- super_agent:{"role": "super_agent", "content": '{"decision": "stop/generate", "reason": "...", "final_output": "..."}'}

注意：
- mode 作为工作流参数传递，不存储在 state 中（节省资源）
- messages 只包含标准 OpenAI 格式的 role 和 content
"""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class WorkflowState:
    """工作流状态

    设计原则：
    - 只存储 messages 列表（标准 OpenAI 格式：role + content）
    - mode 作为工作流参数传递，不在 state 中存储（节省资源）
    - 其他数据通过 property 从 content 中计算获取
    - 不同 role 的 content 结构不同，按约定解析
    """
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # ---- 便捷访问方法 ----

    @property
    def input_text(self) -> str:
        """获取用户输入"""
        if self.messages:
            return self.messages[0].get("content", "")
        return ""

    # ---- generator message ----

    @property
    def current_draft(self) -> str:
        for msg in reversed(self.messages):
            if msg.get("role") == "generator":
                return msg.get("content", "")
        return ""

    # ---- reviewer message (JSON) ----

    @property
    def _last_review_json(self) -> Optional[dict]:
        """获取最后一条 reviewer 消息的 JSON 内容"""
        for msg in reversed(self.messages):
            if msg.get("role") == "reviewer":
                raw = msg.get("content", "")
                if not raw:
                    return None
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
        return None

    @property
    def reviewed_text(self) -> str:
        """原始审查结果文本"""
        for msg in reversed(self.messages):
            if msg.get("role") == "reviewer":
                return msg.get("content", "")
        return ""

    @property
    def review_passed(self) -> bool:
        """审查是否通过"""
        result = self._last_review_json
        return result.get("passed", True) if result else True

    @property
    def review_issues(self) -> list:
        """审查发现的问题"""
        result = self._last_review_json
        return result.get("issues", []) if result else []

    @property
    def optimized_content(self) -> str:
        """审查后优化过的内容"""
        result = self._last_review_json
        if result:
            content = result.get("optimized_content", "")
            if content:
                return content
        return ""

    # ---- super_agent message (JSON) ----

    @property
    def _last_decision_json(self) -> Optional[dict]:
        for msg in reversed(self.messages):
            if msg.get("role") == "super_agent":
                raw = msg.get("content", "")
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
        return None

    @property
    def iteration(self) -> int:
        return sum(1 for m in self.messages if m.get("role") == "generator")

    # ---- 通用方法 ----

    def add_message(self, role: str, content: str) -> None:
        """添加一条消息（标准 OpenAI 格式：role + content）

        Args:
            role: 消息角色（user/generator/reviewer/super_agent）
            content: 消息内容
        """
        message = {"role": role, "content": content}
        self.messages.append(message)

    def get_last_n_messages(self, n: int) -> List[Dict[str, Any]]:
        return self.messages[-n:] if n > 0 else []
