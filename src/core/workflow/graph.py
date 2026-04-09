"""LangGraph 工作流 - StateGraph + 条件边"""
import json
import logging
from langgraph.graph import StateGraph, END

from .state import WorkflowState
from ..agents.generator import GeneratorAgent
from ..agents.reviewer import ReviewerAgent
from ..agents.super_agent import SuperAgent


logger = logging.getLogger(__name__)


def _is_verbose_log():
    """是否打印详细 LLM 日志（有 LangSmith 时不需要）"""
    import os
    return os.environ.get("NAPS_VERBOSE_LLM_LOG", "true").lower() == "true"


class ContentGenerationWorkflow:
    """内容生成工作流

    图结构：
        START → super_agent ──→ END
                 │
                 └─→ generator → reviewer ─┘（循环）

    条件边：super_agent 输出 decision 为 "stop" → END
                                "generate" → generator
    """

    def __init__(self, max_iteration: int = 3):
        self.max_iteration = max_iteration
        self.generator = GeneratorAgent()
        self.reviewer = ReviewerAgent()
        self.super_agent = SuperAgent(max_iteration=max_iteration)
        self._mode = "simple"  # 当前工作模式
        self.app = None  # 延迟构建，因为需要先设置 mode

    def _build_graph(self):
        """构建 LangGraph StateGraph"""
        graph = StateGraph(WorkflowState)

        # 添加节点
        graph.add_node("super_agent", self._super_agent_node)
        graph.add_node("generator", self._generator_node)
        graph.add_node("reviewer", self._reviewer_node)

        # 入口：super_agent 首先判断
        graph.set_entry_point("super_agent")

        # 条件边：super_agent → generator/END
        graph.add_conditional_edges(
            "super_agent",
            self._route_decision,
            {
                "generate": "generator",
                "stop": END,
            }
        )

        # 固定边：generator → reviewer → super_agent
        graph.add_edge("generator", "reviewer")
        graph.add_edge("reviewer", "super_agent")

        return graph.compile()

    # ---- 节点函数 ----

    def _generator_node(self, state: WorkflowState) -> WorkflowState:
        """generator 节点"""
        input_text = state.input_text
        mode = self._mode

        if mode == "professional":
            system_prompt = self.generator._read_prompt("agents/generator_professional.txt")
            user_prompt = f"请根据以下结构化的任务数据生成项目经历汇报：\n\n{input_text}"
        else:
            system_prompt = self.generator._read_prompt("agents/generator_simple.txt")
            user_prompt_template = self.generator._read_prompt("agents/generator_simple_user.txt")
            user_prompt = user_prompt_template.replace("{commits}", input_text)

        # 如果有上一轮的反馈，附加到 prompt 中让 generator 参考
        feedback = self._collect_feedback(state)
        if feedback:
            user_prompt += f"\n\n**上一轮审查反馈（请参考修正）**：\n{feedback}"

        try:
            content = self.generator.llm_client.generate(
                user_prompt=user_prompt,
                system_prompt=system_prompt or None
            )
        except Exception as e:
            logger.error(f"Generator 执行失败: {e}")
            content = ""

        if _is_verbose_log():
            logger.info(f"[Generator] 输出 (前300字): {content[:300]}")
        state.add_message("generator", content)
        return state

    def _collect_feedback(self, state: WorkflowState) -> str:
        """从上一轮 reviewer/super_agent 消息中收集反馈"""
        feedback_parts = []

        # 获取上一轮 reviewer 的问题
        if state.review_issues:
            feedback_parts.append(f"审查发现的问题: {'; '.join(state.review_issues)}")

        # 获取上一轮 super_agent 的原因
        for msg in reversed(state.messages):
            if msg.get("role") == "super_agent":
                try:
                    result = json.loads(msg.get("content", "{}"))
                    reason = result.get("reason", "")
                    if reason and reason not in ("first_run", "no_content_yet", "validation_passed"):
                        feedback_parts.append(f"需要重新生成的原因: {reason}")
                except json.JSONDecodeError:
                    pass
                break

        return "\n".join(feedback_parts)

    def _reviewer_node(self, state: WorkflowState) -> WorkflowState:
        """reviewer 节点"""
        draft = state.current_draft
        mode = self._mode

        if not draft:
            result = {
                "passed": True,
                "issues": ["no_draft_to_review"],
                "optimized_content": ""
            }
            state.add_message("reviewer", json.dumps(result, ensure_ascii=False))
            return state

        template_path = self.reviewer.PROMPTS_DIR / "reviewer_strict.txt"
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
            prompt = template.replace("{mode}", mode).replace("{draft}", draft)
        else:
            raise FileNotFoundError(f"Reviewer prompt 文件不存在: {template_path}")

        try:
            raw_output = self.reviewer.llm_client.generate(prompt)
            result = self.reviewer._parse_output(raw_output)
            if _is_verbose_log():
                logger.info(f"[Reviewer] raw_output: {raw_output[:500]}")
                logger.info(f"[Reviewer] parsed: passed={result.get('passed')}, issues={result.get('issues')}")

            # 检测乱码：如果 optimized_content 质量比 draft 差，丢弃
            optimized = result.get("optimized_content", "")
            if optimized and not self._is_content_coherent(optimized, draft):
                logger.warning(f"[Reviewer] 检测到乱码/不相关内容，丢弃 optimized_content，使用原始草稿")
                result["optimized_content"] = draft
                result["passed"] = True
                result["issues"] = []

            if _is_verbose_log():
                logger.info(f"[Reviewer] optimized_content (前200字): {str(result.get('optimized_content', ''))[:200]}")
        except Exception as e:
            logger.warning(f"Reviewer LLM 调用失败: {e}")
            result = {
                "passed": True,
                "issues": [],
                "optimized_content": draft
            }

        state.add_message("reviewer", json.dumps(result, ensure_ascii=False))
        return state

    def _is_content_coherent(self, content: str, reference: str) -> bool:
        """检测内容是否与参考文本相关（防止乱码）

        通过字符重叠度判断：如果内容中有超过一半的字符在参考文本中没出现过，很可能是乱码
        """
        if not content or not reference:
            return False

        # 提取参考文本中出现的字符集合
        ref_chars = set(reference)

        # 检查内容中的中文字符有多少在参考文本中出现过
        content_chars = set(c for c in content if '\u4e00' <= c <= '\u9fff')
        if not content_chars:
            return False

        overlap = content_chars & ref_chars
        ratio = len(overlap) / len(content_chars)

        if ratio < 0.5:
            logger.warning(f"[质量检测] 字符重叠度过低: {ratio:.2f}，可能是乱码")
            return False
        return True

    def _super_agent_node(self, state: WorkflowState) -> WorkflowState:
        """super_agent 节点：规则判断 + reviewer 结果检查"""
        mode = self._mode
        iteration = state.iteration
        current_content = state.optimized_content or state.current_draft

        if _is_verbose_log():
            logger.info(f"[SuperAgent] iteration={iteration}, current_content (前200字): {str(current_content)[:200]}")

        # ===== 规则层 =====
        decision, reason, final_output = self.super_agent._rule_check(
            current_content, mode, iteration
        )

        # ===== reviewer 检查 =====
        # 规则层决定 stop 时，还要看 reviewer 是否通过
        if decision == "stop" and iteration > 0:
            if not state.review_passed and iteration < self.max_iteration:
                issues = state.review_issues
                decision = "generate"
                reason = f"reviewer_not_passed: {'; '.join(issues) if issues else 'unknown'}"
                final_output = None
                if _is_verbose_log():
                    logger.info(f"[SuperAgent] reviewer 未通过，触发重新生成: {issues}")

        # 首次执行时，如果没有内容，决定生成
        if iteration == 0 and not current_content:
            decision = "generate"
            reason = "first_run"

        # 构建决策 JSON
        result = {
            "decision": decision,
            "reason": reason,
            "final_output": final_output or "",
            "iteration": iteration
        }
        if _is_verbose_log():
            logger.info(f"[SuperAgent] decision={decision}, reason={reason}, final_output_len={len(str(final_output or ''))}")
        state.add_message("super_agent", json.dumps(result, ensure_ascii=False))
        return state

    # ---- 条件边路由函数 ----

    def _route_decision(self, state: WorkflowState) -> str:
        """从 super_agent 最后一条消息读取决策，路由到对应节点"""
        for msg in reversed(state.messages):
            if msg.get("role") == "super_agent":
                try:
                    result = json.loads(msg.get("content", "{}"))
                    decision = result.get("decision", "stop")
                    # 支持的决策：generate, stop
                    if decision == "generate":
                        return "generate"
                    return "stop"
                except json.JSONDecodeError:
                    return "stop"
        # 首次执行时默认生成
        return "generate"

    # ---- 外部接口 ----

    def run(self, input_text: str, mode: str = "simple", **kwargs) -> str:
        """执行工作流

        Args:
            input_text: 输入文本
            mode: simple 或 professional

        Returns:
            最终生成的文本内容
        """
        # 设置模式并构建图（延迟构建以支持模式切换）
        self._mode = mode
        if self.app is None:
            self.app = self._build_graph()

        # 初始化状态
        state = WorkflowState()
        state.add_message("user", input_text)

        # 执行图
        final_state = self.app.invoke(
            state,
            config={"run_name": f"report_{mode}"}
        )

        # LangGraph 返回的是字典（state 序列化后的结果）
        messages = final_state.get("messages", [])

        # 策略：按优先级提取最终内容
        content = self._extract_final_content(messages)

        logger.info(f"工作流完成，mode={mode}，内容长度={len(content)}")
        return content

    def _extract_final_content(self, messages: list) -> str:
        """从消息列表中提取最终内容

        策略：直接从 reviewer 消息提取 optimized_content，
        因为那才是经过审查的最终文本。
        """
        # 1. 从最后一条 reviewer 获取 optimized_content
        for msg in reversed(messages):
            if msg.get("role") == "reviewer":
                try:
                    result = json.loads(msg.get("content", "{}"))
                    optimized = result.get("optimized_content", "")
                    if optimized and isinstance(optimized, str):
                        logger.info(f"从 reviewer 提取 optimized_content，长度={len(optimized)}")
                        return self._ensure_plain_text(optimized)
                    logger.warning(f"reviewer 无 optimized_content，keys={list(result.keys())}")
                except json.JSONDecodeError as e:
                    logger.warning(f"reviewer JSON 解析失败: {e}")
                break

        # 2. 从最后一条 generator 获取草稿
        for msg in reversed(messages):
            if msg.get("role") == "generator":
                content = msg.get("content", "")
                if content:
                    logger.info(f"从 generator 提取草稿，长度={len(content)}")
                    return self._ensure_plain_text(content)

        logger.error("未能从任何节点提取内容")
        return ""

    def _ensure_plain_text(self, content: str) -> str:
        """确保内容是纯文本，不是 JSON 结构"""
        if not content or not isinstance(content, str):
            return ""

        stripped = content.strip()
        if not stripped.startswith("{"):
            return content

        # 内容看起来像 JSON，尝试提取实际文本
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                optimized = parsed.get("optimized_content", "")
                if optimized and isinstance(optimized, str):
                    logger.info(f"_ensure_plain_text: 从嵌套 JSON 提取 optimized_content")
                    return optimized
                final = parsed.get("final_output", "")
                if final and isinstance(final, str):
                    logger.info(f"_ensure_plain_text: 从嵌套 JSON 提取 final_output")
                    return final
        except json.JSONDecodeError:
            pass

        return content
