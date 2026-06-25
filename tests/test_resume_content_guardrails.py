from src.core.validators.resume_content import sanitize_resume_generation


def test_sanitize_drops_cross_project_content_for_exc():
    config = {
        "id": "exc",
        "name": "引流权益兑换系统",
        "description": "引流权益兑换系统，提供支付订单创建、退款、投诉等核心功能。",
        "modules": [
            {"name": "支付订单"},
            {"name": "退款"},
            {"name": "投诉"},
        ],
    }
    result = {
        "description": "引流权益兑换系统，采用Spring Boot架构，提供支付订单创建。",
        "main_contributions": [
            "支付订单：设计并实现支付订单架构，提升系统性能30%",
            "收单结算：处理换汇和跨境支付",
        ],
        "key_achievements": [
            "支持退款自动化处理",
            "完成换汇相关功能",
        ],
    }

    sanitized = sanitize_resume_generation(result, config)

    assert "采用Spring Boot架构" not in sanitized["description"]
    assert sanitized["main_contributions"] == [
        "【引流权益兑换系统】支付订单：使用支付订单，优化系统性能"
    ]
    assert sanitized["key_achievements"] == ["【引流权益兑换系统】支持退款自动化处理"]


def test_sanitize_keeps_naps_financial_modules():
    config = {
        "id": "naps",
        "name": "全球收单",
        "description": "跨境支付收单平台，提供收单、退款、换汇、代付、清结算等金融服务。",
        "modules": [
            {"name": "收单支付"},
            {"name": "换汇"},
            {"name": "代付"},
            {"name": "清结算"},
        ],
    }
    result = {
        "description": config["description"],
        "main_contributions": [
            "收单支付：开发订单创建和支付接口",
            "换汇：支持实时汇率管理",
            "清结算：完成对账功能开发",
            "广告位配置：实现引流策略管理",
        ],
        "key_achievements": [
            "完成代付处理",
            "实现广告投放功能",
        ],
    }

    sanitized = sanitize_resume_generation(result, config)

    assert sanitized["main_contributions"] == [
        "【全球收单】收单支付：开发订单创建和支付接口",
        "【全球收单】换汇：支持实时汇率管理",
        "【全球收单】清结算：完成对账功能开发",
    ]
    assert sanitized["key_achievements"] == ["【全球收单】完成代付处理"]
