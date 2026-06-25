"""Resume content guardrails for generated project summaries."""
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


def sanitize_resume_generation(result: Dict, project_config: Dict) -> Dict:
    """Normalize generated resume fields and drop obvious cross-project content."""
    project_name = project_config.get("name", "")
    description = _clean_description(
        result.get("description") or project_config.get("description", "")
    )

    main_contributions = _sanitize_items(
        result.get("main_contributions", []),
        project_config,
        field="main_contributions",
    )
    key_achievements = _sanitize_items(
        result.get("key_achievements", []),
        project_config,
        field="key_achievements",
    )

    if not main_contributions:
        main_contributions = _fallback_contributions(project_config)
    if not key_achievements:
        key_achievements = _fallback_achievements(project_config)

    return {
        "description": description,
        "main_contributions": _dedupe(main_contributions),
        "key_achievements": _dedupe(key_achievements),
    }


def _clean_description(description: str) -> str:
    """Keep product scope in descriptions and remove architecture boasting."""
    if not description:
        return ""

    cleaned = description.strip()
    patterns = [
        r"采用[^。；;]*?架构[，,。；;]?",
        r"支持分布式事务和分库分表[，,。；;]?",
        r"支持按周动态分表[，,。；;]?",
        r"处理高并发[^。；;]*[，,。；;]?",
        r"支撑高并发[^。；;]*[，,。；;]?",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace("。。", "。").replace("，。", "。").strip(" ，,;；")
    if cleaned and not cleaned.endswith("。"):
        cleaned += "。"
    return cleaned


def _sanitize_items(items: List[str], project_config: Dict, field: str) -> List[str]:
    if not items:
        return []

    sanitized = []
    allowed_modules = {
        module.get("name", "")
        for module in project_config.get("modules", [])
        if module.get("name")
    }

    for item in items:
        text = _normalize_item(str(item), project_config)
        if not text:
            continue
        if _is_cross_project_content(text, project_config):
            logger.info("[resume_content] drop cross-project %s: %s", field, text[:80])
            continue
        if field == "main_contributions" and _is_technical_only(text):
            logger.info("[resume_content] drop technical-only contribution: %s", text[:80])
            continue
        if field == "main_contributions" and not _matches_allowed_module(text, allowed_modules):
            logger.info("[resume_content] drop unknown module contribution: %s", text[:80])
            continue
        sanitized.append(text)

    return sanitized


def _normalize_item(item: str, project_config: Dict) -> str:
    text = item.strip().lstrip("-*●• ").strip()
    if not text:
        return ""

    replacements = [
        (r"设计并实现\s*([^，。；;]*?)架构", r"使用\1"),
        (r"设计\s*([^，。；;]*?)架构", r"使用\1"),
        (r"构建\s*([^，。；;]*?)架构", r"使用\1"),
        (r"支撑高并发场景", "处理业务场景"),
        (r"支撑高并发", "处理业务请求"),
        (r"高并发", "并发"),
        (r"大规模", ""),
        (r"全方位", ""),
        (r"提升系统性能\s*[Xx\d]+%?", "优化系统性能"),
        (r"提升查询速度\s*[Xx\d]+%?", "优化查询性能"),
        (r"节省[^，。；;]*?\s*[Xx\d]+%?", "优化资源使用"),
        (r"提高[^，。；;]*?\s*[Xx\d]+%?", "提升相关能力"),
        (r"降低[^，。；;]*?\s*[Xx\d]+%?", "优化相关成本"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    text = re.sub(r"\s+", " ", text).strip(" ，,;；")
    text = text.replace("。。", "。").replace("，，", "，")

    project_name = project_config.get("name", "")
    if project_name and not text.startswith(f"【{project_name}】"):
        text = f"【{project_name}】{text}"
    return text


def _is_cross_project_content(text: str, project_config: Dict) -> bool:
    project_name = project_config.get("name", "")
    project_desc = project_config.get("description", "")
    has_ad = any(word in project_desc for word in ["广告", "引流", "流量"])

    if not has_ad and any(word in text for word in ["广告", "引流", "流量通道"]):
        return True

    if "引流权益兑换" in project_name or project_config.get("id") == "exc":
        return any(word in text for word in ["收单结算", "换汇", "跨境支付", "代付", "清结算"])

    if "俄罗斯短剧" in project_name:
        return any(word in text for word in ["收单结算", "换汇", "跨境支付", "代付", "清结算"])

    if "全球收单" in project_name or project_config.get("id") == "naps":
        return any(word in text for word in ["广告", "引流", "流量通道", "剧集", "短剧"])

    return False


def _is_technical_only(text: str) -> bool:
    technical_terms = ["分布式事务", "分库分表", "分布式锁", "缓存", "Spring Boot", "微服务架构"]
    business_terms = [
        "支付", "订单", "退款", "投诉", "商户", "活动", "广告位", "剧集", "用户",
        "内容", "收单", "回调", "卡片", "埋点", "换汇", "代付", "清结算", "费率",
        "PPT", "多模态", "图片", "工作流",
    ]
    return any(term in text for term in technical_terms) and not any(
        term in text for term in business_terms
    )


def _matches_allowed_module(text: str, allowed_modules: set) -> bool:
    if not allowed_modules:
        return True
    content = re.sub(r"^【[^】]+】", "", text)
    if "：" not in content:
        return True
    module_name = content.split("：", 1)[0].strip()
    return module_name in allowed_modules


def _fallback_contributions(project_config: Dict) -> List[str]:
    project_name = project_config.get("name", "")
    contributions = []
    for module in project_config.get("modules", [])[:5]:
        name = module.get("name")
        if name:
            contributions.append(f"【{project_name}】{name}：完成相关业务功能开发")
    return contributions or [f"【{project_name}】参与项目业务功能开发"]


def _fallback_achievements(project_config: Dict) -> List[str]:
    project_name = project_config.get("name", "")
    achievements = []
    for module in project_config.get("modules", [])[:3]:
        name = module.get("name")
        if name:
            achievements.append(f"【{project_name}】完成{name}相关功能")
    return achievements or [f"【{project_name}】完成项目相关功能"]


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
