"""Default Commit 分类器 - 将 commit 分类到预定义模块"""
import json
import re
import logging
from typing import List, Dict, Optional
from pathlib import Path

from src.core.llm.client import get_llm_client

logger = logging.getLogger(__name__)


class DefaultCommitClassifier:
    """将 commit 分类到项目预定义的业务模块

    分类策略（优先级）：
    1. 关键词匹配（零 LLM，速度快）
    2. LLM 兜底（关键词匹配不到时）
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "commit" / "default_classify_prompt.txt"

    # 操作类型关键词
    ACTION_KEYWORDS = {
        "修复": ["修复", "fix", "bug", "问题"],
        "重构": ["重构", "refactor", "优化", "重写"],
    }
    DEFAULT_ACTION = "开发"

    # 通用关键词映射（用于增强匹配）
    COMMON_KEYWORD_MAP = {
        # 用户相关
        "user": ["用户管理", "用户订阅", "会员"],
        "登录": ["用户管理"],
        "注册": ["用户管理"],
        "member": ["用户管理", "会员"],
        "vip": ["用户管理", "会员"],
        "subscribe": ["用户管理", "会员"],
        "uuid": ["用户管理"],
        "游客": ["用户管理"],
        "identity": ["用户管理"],
        "auth": ["用户管理"],

        # 订单相关（仅用于支付订单/收单项目）
        "order": ["支付订单", "收单"],
        "purchase": ["支付订单", "收单"],
        "orders": ["支付订单", "收单"],

        # 支付相关（区分不同项目）
        "pay": "skip",  # 太通用，跳过
        "payment": "skip",  # 太通用，跳过
        "alipay": ["支付订单"],
        "wechat": ["支付订单"],
        "wxpay": ["支付订单"],
        "apple": ["用户管理"],  # Apple 支付在短剧项目中是用户订阅的一部分

        # 退款相关
        "refund": ["退款"],

        # 商户相关
        "merchant": ["商户管理"],
        "商户": ["商户管理"],

        # 活动相关
        "activity": ["活动配置"],
        "概率": ["活动配置"],

        # 广告相关
        "ad": ["广告位配置"],
        "引流": ["广告位配置"],

        # 投诉相关
        "complaint": ["投诉处理"],
        "投诉": ["投诉处理"],

        # 剧集相关
        "drama": ["剧集管理"],
        "episode": ["剧集管理"],
        "course": ["剧集管理"],
        "playlet": ["剧集管理"],
        "短剧": ["剧集管理"],

        # 内容相关
        "content": ["内容分发"],
        "分发": ["内容分发"],
        "distribute": ["内容分发"],
        "发布": ["内容分发"],
        "平台": ["内容分发"],

        # 换汇相关
        "exchange": ["换汇"],
        "currency": ["换汇"],
        "汇率": ["换汇"],

        # 代付相关
        "payout": ["代付"],

        # 清结算相关
        "settlement": ["清结算"],
        "清算": ["清结算"],
        "对账": ["清结算"],

        # 收单相关
        "acquire": ["收单"],
        "交易": ["收单"],

        # PPT相关
        "ppt": ["PPT生成"],
        "slide": ["PPT生成"],
        "layout": ["PPT生成"],
        "presentation": ["PPT生成"],

        # 多模态相关
        "whisper": ["多模态输入"],
        "voice": ["多模态输入"],
        "语音": ["多模态输入"],

        # 工作流相关
        "workflow": ["工作流管理"],
        "chatbot": ["工作流管理"],
        "review": ["工作流管理"],

        # 图片相关
        "stable": ["图片生成"],
        "diffusion": ["图片生成"],
        "minicpm": ["图片生成"],
        "image": ["图片生成"],
        "图片": ["图片生成"],
    }

    @classmethod
    def _match_by_keywords(cls, commit_msg: str, modules: List[Dict]) -> Optional[Dict]:
        """关键词匹配（零 LLM）

        增强匹配策略：
        1. 直接匹配模块关键词
        2. 通过通用关键词映射间接匹配

        Args:
            commit_msg: commit 消息
            modules: [{name, keywords}]

        Returns:
            {"module": "退款", "action": "修复", "confidence": 0.9} 或 None
        """
        msg_lower = commit_msg.lower()

        best_match = None
        best_score = 0

        # 构建模块名到关键词的反向映射
        module_name_map = {m["name"]: m for m in modules}

        for module in modules:
            name = module["name"]
            keywords = module.get("keywords", [])

            match_count = 0
            # 直接匹配模块关键词
            for kw in keywords:
                if kw.lower() in msg_lower:
                    match_count += 2  # 直接匹配权重更高

            # 通过通用关键词映射间接匹配
            for common_kw, target_modules in cls.COMMON_KEYWORD_MAP.items():
                if common_kw.lower() in msg_lower:
                    # 跳过标记为 skip 的关键词
                    if target_modules == "skip" or target_modules is True:
                        continue
                    if isinstance(target_modules, list):
                        if name in target_modules:
                            match_count += 1  # 间接匹配权重较低

            if match_count > 0:
                # 匹配度 = 匹配的关键词数 / 总关键词数（归一化）
                score = min(1.0, match_count / max(1, len(keywords)))
                if score > best_score:
                    best_score = score
                    best_match = module

        if best_match:
            action = cls._detect_action(commit_msg)
            confidence = min(0.9, best_score + 0.3)  # 关键词匹配置信度
            logger.debug(f"  [关键词匹配] '{commit_msg[:30]}...' → {best_match['name']} (confidence={confidence:.2f})")
            return {
                "module": best_match["name"],
                "action": action,
                "confidence": confidence
            }

        return None

    @classmethod
    def _detect_action(cls, commit_msg: str) -> str:
        """根据 commit 消息检测操作类型"""
        msg_lower = commit_msg.lower()
        for action, keywords in cls.ACTION_KEYWORDS.items():
            for kw in keywords:
                if kw in msg_lower:
                    return action
        return cls.DEFAULT_ACTION

    @classmethod
    def _classify_by_llm(cls, commit_msg: str, module_names: List[str]) -> Optional[Dict]:
        """LLM 兜底分类

        Args:
            commit_msg: commit 消息
            module_names: 模块名称列表

        Returns:
            {"module": "退款", "action": "开发", "confidence": 0.6} 或 None
        """
        if not cls.PROMPT_PATH.exists():
            logger.warning(f"分类 prompt 文件不存在: {cls.PROMPT_PATH}")
            return None

        prompt_template = cls.PROMPT_PATH.read_text(encoding="utf-8")
        prompt = prompt_template.replace("{modules}", json.dumps(module_names, ensure_ascii=False))
        prompt = prompt.replace("{commit}", commit_msg)

        try:
            llm = get_llm_client()
            response = llm.generate(prompt)
            result = cls._parse_classify_response(response, module_names)
            return result
        except Exception as e:
            logger.warning(f"LLM 分类失败: {e}")
            return None

    @classmethod
    def _parse_classify_response(cls, response: str, module_names: List[str]) -> Optional[Dict]:
        """解析 LLM 分类响应"""
        try:
            # 提取 JSON
            json_str = response.strip()
            if "```" in json_str:
                json_str = re.search(r'```(?:json)?\s*(.*?)\s*```', json_str, re.DOTALL)
                if json_str:
                    json_str = json_str.group(1)

            result = json.loads(json_str)

            module = result.get("module", "unknown")
            action = result.get("action", cls.DEFAULT_ACTION)
            confidence = float(result.get("confidence", 0.5))

            # 验证模块名是否在候选列表中
            if module != "unknown" and module not in module_names:
                logger.warning(f"  [LLM分类] 模块 '{module}' 不在候选列表中，标记为 unknown")
                module = "unknown"

            return {
                "module": module,
                "action": action,
                "confidence": confidence
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"  [LLM分类] 解析失败: {e}, response: {response[:100]}")
            return None

    @classmethod
    def classify(cls, commit_msg: str, modules: List[Dict]) -> Dict:
        """对单个 commit 进行分类

        只使用关键词匹配，不调用 LLM。
        关键词匹配不到的标为 unknown，交给 aggregate 阶段处理。

        Args:
            commit_msg: commit 消息
            modules: [{name, keywords}]

        Returns:
            {"module": "退款", "action": "修复", "confidence": 0.85}
        """
        # 关键词匹配
        result = cls._match_by_keywords(commit_msg, modules)
        if result:
            return result

        # 匹配不到，标为 unknown
        return {
            "module": "unknown",
            "action": cls._detect_action(commit_msg),
            "confidence": 0.0
        }

    @classmethod
    def classify_batch(cls, commits: List[Dict], modules: List[Dict]) -> List[Dict]:
        """批量分类 commits

        Args:
            commits: [{message, hash, date, ...}]
            modules: [{name, keywords}]

        Returns:
            [{module, action, confidence, message, hash}]
        """
        if not modules:
            logger.warning("  [分类] 无 modules 配置，全部标记为 unknown")
            return [
                {"module": "unknown", "action": cls.DEFAULT_ACTION, "confidence": 0.0,
                 "message": c.get("message", ""), "hash": c.get("hash", "")}
                for c in commits
            ]

        results = []
        keyword_count = 0
        unknown_count = 0

        for commit in commits:
            msg = commit.get("message", "")
            result = cls.classify(msg, modules)
            result["message"] = msg
            result["hash"] = commit.get("hash", "")

            if result["module"] == "unknown":
                unknown_count += 1
            else:
                keyword_count += 1

            results.append(result)

        logger.info(f"  [分类] 完成: {len(results)} 条 (关键词={keyword_count}, unknown={unknown_count})")
        return results
