"""简历生成工作流 - 独立 LangGraph 图

图结构（线性，无循环）：
    START → filter_resume → classify → aggregate → generate → END

状态：复用 WorkflowState，通过 messages 传递数据
每个节点读最后一条消息、写一条新消息。
"""
import json
import logging
from pathlib import Path

from langgraph.graph import StateGraph, END

from .state import WorkflowState
from ..git.default_classifier import DefaultCommitClassifier
from ..git.module_aggregator import ModuleAggregator
from ..git.task_classifier import CommitFilter
from ..llm.client import get_llm_client

logger = logging.getLogger(__name__)


class ResumeGenerationWorkflow:
    """简历生成工作流

    设计原则：
    - 复用 WorkflowState，通过 messages 传递数据
    - 每个 add_message(role, json_content) 传递中间结果
    - 线性流程，无循环
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "resume" / "resume_module_generator.txt"

    def _build_graph(self):
        """构建 LangGraph StateGraph"""
        graph = StateGraph(WorkflowState)

        # 添加节点
        graph.add_node("filter_resume", self._filter_node)
        graph.add_node("classify", self._classify_node)
        graph.add_node("aggregate", self._aggregate_node)
        graph.add_node("generate", self._generate_node)

        # 线性边
        graph.set_entry_point("filter_resume")
        graph.add_edge("filter_resume", "classify")
        graph.add_edge("classify", "aggregate")
        graph.add_edge("aggregate", "generate")
        graph.add_edge("generate", END)

        return graph.compile()

    # ---- 节点函数 ----

    def _filter_node(self, state: WorkflowState) -> WorkflowState:
        """读 user 消息 → 过滤低质量 commit → 写 filtered 消息"""
        payload = json.loads(state.input_text)
        commits = payload["commits"]

        filtered, stats = CommitFilter.filter_commits_for_resume(commits)
        logger.info(f"[filter_resume] {len(commits)} → {len(filtered)} (过滤: {stats})")

        state.add_message("filtered", json.dumps(filtered, ensure_ascii=False))
        return state

    def _classify_node(self, state: WorkflowState) -> WorkflowState:
        """读最后一条消息(filtered) → 分类到模块 → 写 classified 消息"""
        filtered = json.loads(state.messages[-1]["content"])
        payload = json.loads(state.input_text)
        modules = payload["project_config"].get("modules", [])

        if not modules:
            logger.warning("[classify] 无 modules 配置，全部标记 unknown")
            classified = [
                {"module": "unknown", "action": "开发", "confidence": 0.0,
                 "message": c.get("message", ""), "hash": c.get("hash", "")}
                for c in filtered
            ]
        else:
            classified = DefaultCommitClassifier.classify_batch(filtered, modules)

        state.add_message("classified", json.dumps(classified, ensure_ascii=False))
        return state

    def _aggregate_node(self, state: WorkflowState) -> WorkflowState:
        """读最后一条消息(classified) → 按模块聚合 → 写 module_stats 消息"""
        classified = json.loads(state.messages[-1]["content"])
        payload = json.loads(state.input_text)
        modules = payload["project_config"].get("modules", [])

        stats = ModuleAggregator.aggregate(classified, modules)

        state.add_message("module_stats", json.dumps(stats, ensure_ascii=False))
        return state

    def _generate_node(self, state: WorkflowState) -> WorkflowState:
        """读 module_stats + project_config → LLM 受控表达 → 写 output 消息"""
        stats = json.loads(state.messages[-1]["content"])
        payload = json.loads(state.input_text)
        config = payload["project_config"]

        if not stats:
            logger.warning("[generate] 无有效模块，使用 config fallback")
            output = self._generate_from_config(config)
            state.add_message("output", json.dumps(output, ensure_ascii=False))
            return state

        output = self._generate_from_stats(stats, config)
        state.add_message("output", json.dumps(output, ensure_ascii=False))
        return state

    # ---- 生成逻辑 ----

    def _generate_from_stats(self, stats: list, config: dict) -> dict:
        """基于模块统计 + 项目配置，用 LLM 生成简历内容"""
        if not self.PROMPT_PATH.exists():
            logger.warning(f"[generate] Prompt 文件不存在，使用 fallback: {self.PROMPT_PATH}")
            return self._generate_from_config(config)

        prompt_template = self.PROMPT_PATH.read_text(encoding="utf-8")

        # 构建模块统计描述
        stats_text = "\n".join(
            f"- {s['name']}: {s['count']} 次提交 (操作: {', '.join(s['actions'])})"
            for s in stats
        )

        prompt = prompt_template.replace("{project_name}", config.get("name", ""))
        prompt = prompt.replace("{description}", config.get("description", ""))
        prompt = prompt.replace("{tech_stack}", ", ".join(config.get("tech_stack", [])))
        prompt = prompt.replace("{module_stats}", stats_text)

        logger.info(f"[generate] 开始 LLM 生成，项目: {config.get('name', 'unknown')}")
        logger.debug(f"[generate] 模块统计: {stats_text}")

        try:
            llm = get_llm_client()
            response = llm.generate(prompt)
            logger.info(f"[generate] LLM 响应 (前300字): {response[:300]}")

            result = self._parse_generate_response(response, config)
            logger.info(f"[generate] 解析成功，main_contributions 数量: {len(result.get('main_contributions', []))}")
            return result
        except Exception as e:
            logger.error(f"[generate] LLM 生成失败: {e}, 使用 config fallback")
            return self._generate_from_config(config)

    def _generate_from_config(self, config: dict) -> dict:
        """Fallback: 直接用 config 生成（不调用 LLM）

        根据模块名称生成多样化的描述，避免重复"相关功能开发和维护"
        """
        modules = config.get("modules", [])
        description = config.get("description", "")
        project_name = config.get("name", "")

        # 根据模块名称和关键词生成多样化的描述
        def generate_contribution(module: dict) -> str:
            """根据模块生成贡献描述"""
            name = module["name"]
            keywords = module.get("keywords", [])

            # 根据关键词选择合适的动词和描述
            if any(kw in keywords for kw in ["支付", "pay", "订单", "交易"]):
                return f"{name}：开发支付订单创建和管理功能"
            elif any(kw in keywords for kw in ["退款", "refund"]):
                return f"{name}：实现退款审核和自动化退款流程"
            elif any(kw in keywords for kw in ["投诉", "complaint"]):
                return f"{name}：支持用户投诉工单流转和处理"
            elif any(kw in keywords for kw in ["商户", "merchant", "入驻", "费率"]):
                return f"{name}：完成商户入驻审核和费率配置功能"
            elif any(kw in keywords for kw in ["活动", "activity", "配置", "概率"]):
                return f"{name}：负责活动配置和概率规则管理"
            elif any(kw in keywords for kw in ["广告", "ad", "引流", "广告位"]):
                return f"{name}：实现广告位配置和引流策略管理"
            elif any(kw in keywords for kw in ["收单", "acquire"]):
                return f"{name}：开发收单功能"
            elif any(kw in keywords for kw in ["换汇", "exchange", "汇率", "currency"]):
                return f"{name}：支持实时换汇和汇率管理"
            elif any(kw in keywords for kw in ["代付", "payout"]):
                return f"{name}：实现代付审核和批量代付功能"
            elif any(kw in keywords for kw in ["清结算", "settlement", "清算"]):
                return f"{name}：完成清结算和对账功能开发"
            elif any(kw in keywords for kw in ["剧集", "drama", "episode", "内容管理"]):
                return f"{name}：完成剧集分类和内容发布功能"
            elif any(kw in keywords for kw in ["订阅", "subscribe", "member", "VIP", "会员"]):
                return f"{name}：实现用户订阅和会员权益管理"
            elif any(kw in keywords for kw in ["PPT", "slide", "layout"]):
                return f"{name}：完成PPT生成和幻灯片布局功能"
            elif any(kw in keywords for kw in ["多模态", "语音", "Whisper", "输入"]):
                return f"{name}：支持多模态输入和语音识别功能"
            elif any(kw in keywords for kw in ["工作流", "workflow", "Chatbot", "Review"]):
                return f"{name}：实现工作流管理和内容循环优化"
            elif any(kw in keywords for kw in ["图片", "Stable", "Diffusion", "MiniCPM"]):
                return f"{name}：集成图片生成模型和相关功能"
            else:
                # 默认描述，使用不同动词避免重复
                verbs = ["负责", "实现", "完成", "支持", "开发"]
                import random
                verb = random.choice(verbs)
                return f"{name}：{verb}相关功能开发和维护"

        # ⚠️ 关键修复：添加项目名称前缀，确保 company_summarizer 能区分项目
        main_contributions = [
            f"【{project_name}】{generate_contribution(m)}"
            for m in modules[:5]
        ]

        # 生成多样化的关键成果
        def generate_achievement(module: dict) -> str:
            """根据模块生成关键成果"""
            name = module["name"]
            keywords = module.get("keywords", [])

            if any(kw in keywords for kw in ["支付", "pay", "订单", "收单", "交易"]):
                return f"完成支付订单模块全流程开发"
            elif any(kw in keywords for kw in ["退款", "refund"]):
                return f"实现自动化退款流程"
            elif any(kw in keywords for kw in ["投诉", "complaint"]):
                return f"支持投诉工单流转处理"
            elif any(kw in keywords for kw in ["商户", "merchant", "入驻"]):
                return f"完成商户入驻审核功能"
            elif any(kw in keywords for kw in ["活动", "activity"]):
                return f"实现活动配置和概率管理"
            elif any(kw in keywords for kw in ["广告", "ad", "引流"]):
                return f"完成广告位配置功能"
            elif any(kw in keywords for kw in ["换汇", "exchange"]):
                return f"支持实时换汇功能"
            elif any(kw in keywords for kw in ["代付", "payout"]):
                return f"实现批量代付处理"
            elif any(kw in keywords for kw in ["清结算", "settlement"]):
                return f"完成清结算和对账系统"
            elif any(kw in keywords for kw in ["剧集", "drama"]):
                return f"负责剧集内容管理模块"
            elif any(kw in keywords for kw in ["订阅", "subscribe", "会员"]):
                return f"实现用户订阅和会员管理"
            elif any(kw in keywords for kw in ["PPT", "slide"]):
                return f"完成PPT生成核心功能"
            elif any(kw in keywords for kw in ["多模态", "语音"]):
                return f"支持多模态输入功能"
            elif any(kw in keywords for kw in ["工作流", "workflow"]):
                return f"实现循环工作流优化机制"
            elif any(kw in keywords for kw in ["图片", "Stable"]):
                return f"集成图片生成模型"
            else:
                return f"完成{name}相关功能开发"

        # ⚠️ 关键修复：添加项目名称前缀，确保 company_summarizer 能区分项目
        key_achievements = [
            f"【{project_name}】{generate_achievement(m)}"
            for m in modules[:3]
        ]

        return {
            "description": description,
            "main_contributions": main_contributions,
            "key_achievements": key_achievements
        }

    def _parse_generate_response(self, response: str, config: dict) -> dict:
        """解析 LLM 生成响应"""
        import re

        try:
            # 提取 JSON
            json_str = response.strip()
            logger.debug(f"[generate] 原始响应长度: {len(response)}, 提取前: {len(json_str)}")

            if "```" in json_str:
                match = re.search(r'```(?:json)?\s*(.*?)\s*```', json_str, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    logger.debug(f"[generate] 从代码块提取 JSON，长度: {len(json_str)}")

            # 尝试找到 JSON 起止
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]
                logger.debug(f"[generate] 提取 JSON 对象，长度: {len(json_str)}")

            result = json.loads(json_str)
            logger.info(f"[generate] JSON 解析成功")

            # 验证必需字段
            if "main_contributions" not in result or not isinstance(result["main_contributions"], list):
                logger.warning(f"[generate] 缺少 main_contributions 或格式错误，使用 fallback")
                return self._generate_from_config(config)

            if "key_achievements" not in result or not isinstance(result["key_achievements"], list):
                logger.warning(f"[generate] 缺少 key_achievements 或格式错误，使用 fallback")
                return self._generate_from_config(config)

            # 确保 description 使用配置中的描述
            if config.get("description"):
                result["description"] = config["description"]

            return {
                "description": result.get("description", config.get("description", "")),
                "main_contributions": result.get("main_contributions", []),
                "key_achievements": result.get("key_achievements", [])
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[generate] JSON 解析失败: {e}, 响应内容: {response[:200]}, 使用 config fallback")
            return self._generate_from_config(config)

    # ---- 外部接口 ----

    def run(self, raw_commits: list, project_config: dict) -> dict:
        """执行简历生成工作流

        Args:
            raw_commits: 原始 commit 列表
            project_config: 项目配置（包含 modules, description 等）

        Returns:
            {"description", "main_contributions", "key_achievements"}
        """
        logger.info(f"[ResumeWorkflow] 开始处理: {project_config.get('name', 'unknown')}, {len(raw_commits)} 条 commits")

        # 只提取 commit 中需要的字段，避免 datetime 序列化问题
        serializable_commits = [
            {"message": c.get("message", ""), "hash": c.get("hash", ""),
             "date": str(c.get("date", ""))}
            for c in raw_commits
        ]

        state = WorkflowState()
        payload = json.dumps({
            "commits": serializable_commits,
            "project_config": project_config
        }, ensure_ascii=False)
        state.add_message("user", payload)

        # 执行图
        app = self._build_graph()
        result = app.invoke(state, config={"run_name": "resume_generation"})

        # 从最后一条 output 消息提取结果
        output = self._extract_output(result)
        logger.info(f"[ResumeWorkflow] 完成: {project_config.get('name', 'unknown')}")
        return output

    def _extract_output(self, final_state: dict) -> dict:
        """从最终 state 中提取 output"""
        messages = final_state.get("messages", [])

        for msg in reversed(messages):
            if msg.get("role") == "output":
                try:
                    return json.loads(msg.get("content", "{}"))
                except json.JSONDecodeError:
                    continue

        logger.warning("[ResumeWorkflow] 未找到 output 消息")
        return {}
