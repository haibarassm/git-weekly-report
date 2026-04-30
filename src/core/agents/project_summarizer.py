"""项目总结 Agent - 压缩大量 commit 信息"""
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
import json
import logging

from src.core.llm.client import get_llm_client

logger = logging.getLogger(__name__)


@dataclass
class ProjectSummary:
    """项目摘要"""
    project_id: str
    description: str
    technical_highlights: str
    key_achievements: List[str]
    main_contributions: List[str]


class ProjectSummarizerAgent:
    """将大量 commit 信息压缩成结构化摘要

    用于简历生成场景，将项目的所有提交记录压缩为：
    - 技术亮点（2-3 句话）
    - 关键成果（3-5 条）
    - 主要贡献（按模块分类）
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "resume" / "project_summarizer.txt"

    def __init__(self):
        self.llm = get_llm_client()
        self._load_prompt()

    def _load_prompt(self):
        """加载提示词模板"""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"提示词文件不存在: {self.PROMPT_PATH}")
        self._prompt = self.PROMPT_PATH.read_text(encoding='utf-8')

    def summarize(self, aggregated_commits: List[Dict], project_config: Dict) -> ProjectSummary:
        """生成项目摘要

        Args:
            aggregated_commits: 聚合后的 commit 列表（已分类）
            project_config: 项目配置

        Returns:
            ProjectSummary
        """
        logger = logging.getLogger(__name__)

        context = self._build_context(aggregated_commits, project_config)
        logger.info(f">>> [项目总结] 项目: {project_config['name']}")
        logger.info(f">>> [项目总结] 输入: {len(aggregated_commits)} 个聚合组")

        try:
            # 使用 replace 避免花括号冲突
            prompt = self._prompt.replace("{context}", context)
            response = self.llm.generate(prompt)
            logger.info(f">>> [项目总结] LLM 原始响应 (前300字符): {response[:300]}...")
            summary = self._parse_summary(response, project_config["id"], project_config)
            logger.info(f">>> [项目总结] 完成: {summary.technical_highlights[:50]}...")
            return summary
        except Exception as e:
            logger.warning(f"项目总结失败: {e}，使用降级策略")
            return self._fallback_summary(aggregated_commits, project_config)

    def _build_context(self, commits: List[Dict], project_config: Dict) -> str:
        """构建 LLM 输入（压缩格式）"""
        project_name = project_config['name']
        project_desc = project_config.get('description', '')

        # 检查项目描述中的业务领域
        has_ad = any(word in project_desc for word in ['广告', '引流', '流量'])

        parts = [
            f"项目名称: {project_name}",
            f"技术栈: {', '.join(project_config.get('tech_stack', []))}",
            f"总提交数: {sum(c.get('task_count', 0) for c in commits)}",
        ]

        # 添加项目描述（如果配置中有）
        if project_desc:
            parts.append(f"项目描述: {project_desc}")

        # 添加业务领域提示
        if has_ad:
            parts.append(f"**提示：此项目包含广告引流功能，必须在主要贡献中体现**")
        else:
            parts.append(f"**提示：此项目不包含广告引流功能，绝对不能写'流量通道'、'广告投放'等内容**")

        # 按类型分组统计
        by_type = {}
        for commit in commits:
            ctype = commit.get("type", "other")
            if ctype not in by_type:
                by_type[ctype] = []
            by_type[ctype].append(commit)

        for ctype, items in by_type.items():
            parts.append(f"\n## {ctype.upper()} ({len(items)} 组)")
            # 每类只取代表性的 5-10 条
            for item in items[:5]:
                tasks = item.get('tasks', [])[:3]  # 每组最多 3 个任务
                for task in tasks:
                    parts.append(f"  - {task[:60]}")

        return "\n".join(parts)

    def _parse_summary(self, response: str, project_id: str, project_config: Dict = None) -> ProjectSummary:
        """解析 LLM 响应"""
        logger = logging.getLogger(__name__)

        # 处理 LangChain 流式响应格式 [{"type":"text","text":"..."}]
        if response.strip().startswith('['):
            try:
                chunks = json.loads(response)
                response = ''.join(chunk.get('text', '') for chunk in chunks)
                logger.info(f"从 LangChain 格式提取文本，长度: {len(response)}")
            except json.JSONDecodeError as e:
                logger.warning(f"LangChain 格式解析失败: {e}")
                pass  # 不是流式格式，继续处理

        # 清理响应：移除 markdown 代码块标记
        cleaned = response.strip()
        cleaned = cleaned.replace('```json', '').replace('```', '')
        cleaned = cleaned.strip()

        # 查找 JSON 对象的起始和结束位置
        json_start = cleaned.find('{')
        if json_start < 0:
            logger.warning(f"未找到 JSON 起始，使用文本解析。响应内容: {response[:200]}...")
            return self._parse_text_summary(response, project_id, project_config)

        # 匹配括号找到 JSON 结束位置
        brace_count = 0
        json_end = -1
        for i in range(json_start, len(cleaned)):
            if cleaned[i] == '{':
                brace_count += 1
            elif cleaned[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i
                    break

        if json_end < 0:
            logger.warning(f"未找到 JSON 结束，使用文本解析")
            return self._parse_text_summary(response, project_id, project_config)

        json_str = cleaned[json_start:json_end + 1]
        logger.info(f"提取的 JSON 长度: {len(json_str)}")
        logger.info(f"提取的 JSON 预览: {json_str[:300]}...")

        try:
            data = json.loads(json_str)
            # 优先使用配置中的 description（如果配置有的话）
            final_description = data.get("description", "").strip()
            if project_config and project_config.get('description'):
                # 如果配置中有 description，强制使用配置中的
                final_description = project_config['description']
                logger.info(f">>> [项目总结] 强制使用配置中的项目描述")

            # 清理高大上的描述
            final_description = self._clean_high_level_description(final_description)

            # 过滤关键成果和主要贡献中的夸大内容
            key_achievements = self._filter_achievements(data.get("key_achievements", []), project_config)
            main_contributions = self._filter_contributions(data.get("main_contributions", []), project_config)

            return ProjectSummary(
                project_id=project_id,
                description=final_description,
                technical_highlights=data.get("technical_highlights", ""),
                key_achievements=key_achievements,
                main_contributions=main_contributions
            )
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}，使用文本解析")
            logger.info(f"JSON 片段: {json_str[:500]}...")
            return self._parse_text_summary(response, project_id, project_config)

    def _parse_text_summary(self, response: str, project_id: str, project_config: Dict = None) -> ProjectSummary:
        """解析文本格式响应"""
        lines = response.split('\n')
        description = ""
        technical_highlights = ""
        key_achievements = []
        main_contributions = []

        current_section = None
        for line in lines:
            line = line.strip()
            if "项目描述" in line or "description" in line:
                current_section = "description"
            elif "技术亮点" in line or "technical_highlights" in line:
                current_section = "highlights"
            elif "关键成果" in line or "key_achievements" in line:
                current_section = "achievements"
            elif "主要贡献" in line or "main_contributions" in line:
                current_section = "contributions"
            elif line.startswith(('- ', '• ', '* ')):
                content = line[2:].strip()
                if current_section == "achievements":
                    key_achievements.append(content)
                elif current_section == "contributions":
                    main_contributions.append(content)
            elif line and not line.startswith('#'):
                if current_section == "highlights":
                    technical_highlights += line + " "
                elif current_section == "description":
                    description += line + " "

        # 优先使用配置中的 description（如果 LLM 返回的为空或待补充）
        final_description = description.strip()
        if not final_description or final_description == "项目描述待补充":
            if project_config and project_config.get('description'):
                final_description = project_config['description']
                logger.info(f">>> [项目总结] 使用配置中的项目描述")
            else:
                final_description = "项目描述待补充"

        # 清理高大上的描述
        final_description = self._clean_high_level_description(final_description)

        # 过滤关键成果和主要贡献中的夸大内容
        key_achievements = self._filter_achievements(key_achievements, project_config)
        main_contributions = self._filter_contributions(main_contributions, project_config)

        return ProjectSummary(
            project_id=project_id,
            description=final_description,
            technical_highlights=technical_highlights.strip() or "技术亮点待补充",
            key_achievements=key_achievements,
            main_contributions=main_contributions
        )

    def _clean_high_level_description(self, description: str) -> str:
        """清理产品描述中的高大上内容，保留业务信息"""
        if not description:
            return description

        import re

        # 只清理明确的夸大描述，保留所有业务内容
        # 去掉"采用XXX微服务架构"、"支持分布式事务和分库分表处理高并发"等
        description = re.sub(r'采用[^。]+?微服务架构[^。]*?。', '', description)
        description = re.sub(r'采用[^。]+?分布式架构[^。]*?。', '', description)
        description = re.sub(r'支持分布式事务和分库分表处理高并发[^。]*?。', '', description)
        description = re.sub(r'支持按周动态分表处理高并发场景', '', description)
        description = re.sub(r'处理高并发[^，。]*', '', description)
        # 去掉"采用分库分表和 RabbitMQ 异步处理架构"，保留"采用 RabbitMQ 异步处理"
        description = re.sub(r'采用分库分表和 RabbitMQ 异步处理架构', '采用 RabbitMQ 异步处理', description)

        # 清理多余的句号和空格
        description = description.replace('。。', '。').strip()
        if description.endswith('，'):
            description = description[:-1] + '。'
        if description.endswith('。。'):
            description = description[:-1] + '。'
        if not description.endswith('。'):
            description += '。'

        return description

    def _filter_achievements(self, achievements: List[str], project_config: Dict) -> List[str]:
        """过滤关键成果中的夸大内容"""
        if not achievements:
            return achievements

        project_desc = project_config.get('description', '')
        has_ad = any(word in project_desc for word in ['广告', '引流', '流量'])
        has_sharding = '分库分表' in project_desc

        filtered = []
        for achievement in achievements:
            original = achievement
            # 智能替换夸大词汇，而不是直接删除
            import re

            # 替换规则列表（更全面，具体规则优先）
            replacements = [
                # 先处理具体的、最荒谬的描述
                (r'设计并实现\s+分库分表\s+架构', '使用分库分表'),
                (r'设计\s+分库分表\s+架构', '使用分库分表'),
                (r'设计并实现\s+Spring Boot\s+架构', '使用 Spring Boot'),
                (r'设计\s+Spring Boot\s+架构', '使用 Spring Boot'),
                (r'设计并实现\s+Spring\s+Cloud', '使用 Spring Cloud'),
                (r'设计\s+Spring\s+Cloud\s+架构', '使用 Spring Cloud'),
                (r'设计并实现\s+分布式缓存\s+架构', '使用分布式缓存'),
                (r'设计\s+分布式缓存\s+架构', '使用分布式缓存'),
                (r'设计并实现\s+分布式事务\s+架构', '使用分布式事务'),
                (r'设计\s+分布式事务\s+架构', '使用分布式事务'),
                (r'设计微服务架构', '使用微服务'),
                (r'设计循环工作流', '开发循环工作流'),
                (r'设计并实施\s+\w+\s+架构', '实现'),
                (r'设计并实施.*?架构', '实现'),
                (r'设计并实现.*?架构', '实现'),  # 通用的放在后面
                (r'设计.*?架构', '实现'),
                (r'构建.*?架构', '使用'),
                (r'构建核心模块', '开发核心功能'),
                (r'支撑高并发场景', '处理高并发'),
                (r'支撑高并发', '处理高并发'),
                (r'实现高可用性和伸缩性', '实现系统高可用'),
                # 处理假数字（X%、30%、20%、15%、25%、40% 等）
                (r'提升系统性能\s+[X\d]+%', '优化系统性能'),
                (r'提升查询速度\s+[X\d]+', '优化查询性能'),
                (r'提升系统响应速度\s+[X\d]+', '提升系统响应速度'),
                (r'减少系统负载\s+[X\d]+', '降低系统负载'),
                (r'节省.*?资源占用\s+[X\d]+', '降低资源占用'),
                (r'节省开发时间\s+[X\d]+', '提高开发效率'),
                (r'提高用户体验度\s+[X\d]+', '提升用户体验'),
                (r'提高交易安全性\s+[X\d]+', '提高交易安全性'),
                (r'降低人工成本\s+[X\d]+', '降低人工成本'),
                (r'节省.*?\s+[X\d]+', '优化'),
                (r'提高.*?[X\d]+%', '提升'),
                (r'输出精度提高\s+[X\d]+', '提高输出精度'),
            ]

            modified = original
            for pattern, replacement in replacements:
                modified = re.sub(pattern, replacement, modified)

            # 如果修改后内容太短或还是包含夸大词汇，则过滤
            if len(modified.strip()) < 5:
                logger.info(f">>> [项目总结] 过滤过短成果: {original[:50]}")
                continue

            # 检查是否还包含严重的禁止词汇
            remaining_forbidden = ['设计并实现', '设计并实施', '设计微服务架构', '支撑高并发场景', '设计 Spring Boot']
            if any(word in modified for word in remaining_forbidden):
                logger.info(f">>> [项目总结] 过滤夸大成果: {modified[:50]}")
                continue

            # 如果项目没有广告，过滤掉广告相关内容
            if not has_ad and any(word in modified for word in ['广告', '引流', '流量通道', '流量']):
                logger.info(f">>> [项目总结] 过滤非项目内容: {modified[:50]}")
                continue

            # 如果项目没有分库分表，过滤掉分库分表相关内容
            if not has_sharding and '分库分表' in modified:
                logger.info(f">>> [项目总结] 过滤非项目内容: {modified[:50]}")
                continue

            if modified != original:
                logger.info(f">>> [项目总结] 替换成果: {original[:30]}... → {modified[:30]}...")

            filtered.append(modified)

        return filtered if filtered else ["关键成果待补充"]

    def _filter_contributions(self, contributions: List[str], project_config: Dict) -> List[str]:
        """过滤主要贡献中的夸大内容"""
        if not contributions:
            return contributions

        project_desc = project_config.get('description', '')
        has_ad = any(word in project_desc for word in ['广告', '引流', '流量'])

        filtered = []
        for contribution in contributions:
            original = contribution
            # 智能替换夸大词汇，而不是直接删除
            import re

            # 替换规则列表（更全面）
            replacements = [
                # 先处理具体的、最荒谬的描述
                (r'设计并实现\s+分库分表\s+架构', '使用分库分表'),
                (r'设计\s+分库分表\s+架构', '使用分库分表'),
                (r'设计并实现\s+Spring Boot\s+架构', '使用 Spring Boot'),
                (r'设计\s+Spring Boot\s+架构', '使用 Spring Boot'),
                (r'设计并实现\s+Spring\s+Cloud', '使用 Spring Cloud'),
                (r'设计\s+Spring\s+Cloud\s+架构', '使用 Spring Cloud'),
                (r'设计并实现\s+分布式缓存\s+架构', '使用分布式缓存'),
                (r'设计\s+分布式缓存\s+架构', '使用分布式缓存'),
                (r'设计并实现\s+分布式事务\s+架构', '使用分布式事务'),
                (r'设计\s+分布式事务\s+架构', '使用分布式事务'),
                (r'设计微服务架构', '使用微服务'),
                (r'设计循环工作流', '开发循环工作流'),
                (r'设计并实施\s+\w+\s+架构', '实现'),
                (r'设计并实施.*?架构', '实现'),
                (r'设计并实现.*?架构', '实现'),  # 通用的放在后面
                (r'设计.*?架构', '实现'),
                (r'构建.*?架构', '使用'),
                (r'构建核心模块', '开发核心功能'),
                # 处理假数字
                (r'提升系统性能\s+[X\d]+%', '优化系统性能'),
                (r'节省.*?资源占用\s+[X\d]+', '降低资源占用'),
                (r'提高用户体验度\s+[X\d]+', '提升用户体验'),
                (r'提高交易安全性\s+[X\d]+', '提高交易安全性'),
            ]

            modified = original
            for pattern, replacement in replacements:
                modified = re.sub(pattern, replacement, modified)

            # 根据项目类型智能过滤
            project_name = project_config.get('name', '')

            # ChatPPT 项目：保留内容生成、工作流管理等相关内容
            if 'ChatPPT' in project_name or 'chatppt' in project_name.lower():
                # 只过滤掉明显的夸大词汇（已经通过上面的替换处理了）
                filtered.append(modified)
                continue

            # 其他项目：如果没有广告，过滤掉广告相关内容
            if not has_ad and any(word in modified for word in ['广告', '引流', '流量通道', '流量']):
                logger.info(f">>> [项目总结] 过滤非项目贡献: {modified[:50]}")
                continue

            # 过滤项目间混淆的内容
            # exc 项目不应该有 naps 的"收单结算"、"换汇"等内容
            if '引流权益兑换' in project_name or 'exc' in project_name.lower():
                if any(word in modified for word in ['收单结算', '换汇', '跨境支付', '代付', '清结算']):
                    logger.info(f">>> [项目总结] 过滤 naps 内容: {modified[:50]}")
                    continue
                # 过滤技术手段
                if any(word in modified for word in ['支持分布式事务', '支持分库分表']):
                    logger.info(f">>> [项目总结] 过滤技术手段: {modified[:50]}")
                    continue

            # naps 项目不应该有其他项目的广告内容
            if '全球收单' in project_name or 'naps' in project_name.lower():
                if any(word in modified for word in ['广告', '流量通道', '引流']):
                    logger.info(f">>> [项目总结] 过滤广告内容: {modified[:50]}")
                    continue
                # 过滤技术手段
                if any(word in modified for word in ['支持分布式事务', '支持分库分表']):
                    logger.info(f">>> [项目总结] 过滤技术手段: {modified[:50]}")
                    continue

            # 俄罗斯短剧项目不应该有 naps 的内容
            if '俄罗斯短剧' in project_name or 'Russian' in project_name:
                if any(word in modified for word in ['收单结算', '换汇', '跨境支付']):
                    logger.info(f">>> [项目总结] 过滤 naps 内容: {modified[:50]}")
                    continue

            # 过滤掉太笼统的描述
            if '核心模块：支付收单、退款结算、商户管理' in modified:
                # 如果有广告，改为流量通道模块；否则改为支付通道模块
                if has_ad:
                    filtered.append("流量通道模块：广告投放和引流")
                    filtered.append("支付通道模块：对接支付渠道")
                else:
                    filtered.append("支付通道模块：对接多个支付渠道")
                logger.info(f">>> [项目总结] 替换笼统描述")
                continue

            # 检查是否还包含严重的夸大词汇
            remaining_forbidden = ['设计并实现', '设计并实施', '设计微服务架构', '支撑高并发场景']
            if any(word in modified for word in remaining_forbidden):
                logger.info(f">>> [项目总结] 过滤夸大贡献: {modified[:50]}")
                continue

            if modified != original:
                logger.info(f">>> [项目总结] 替换贡献: {original[:30]}... → {modified[:30]}...")

            filtered.append(modified)

        return filtered if filtered else ["主要贡献待补充"]

    def _fallback_summary(self, commits: List[Dict], project_config: Dict) -> ProjectSummary:
        """降级策略：基于规则生成摘要"""
        # 统计类型分布
        type_counts = {}
        for commit in commits:
            ctype = commit.get("type", "other")
            type_counts[ctype] = type_counts.get(ctype, 0) + commit.get('task_count', 0)

        # 项目描述：优先使用配置中的描述
        if project_config.get('description'):
            description = project_config['description']
        else:
            # 如果没有配置描述，基于技术栈生成
            tech_stack = ', '.join(project_config.get('tech_stack', []))
            description = f"{project_config['name']}项目，使用 {tech_stack} 开发"

        # 技术亮点：基于技术栈
        tech_stack = project_config.get('tech_stack', [])
        if tech_stack:
            # 提取主要技术（前5个）
            main_tech = tech_stack[:5]
            tech_highlights = f"使用 {', '.join(main_tech)} 等技术"
        else:
            tech_highlights = "使用相关技术栈"

        # 关键成果：基于类型分布生成更有意义的内容
        achievements = []
        type_mapping = {
            'FEATURE': '新功能开发',
            'REFACTOR': '代码重构优化',
            'FIX': 'Bug修复',
            'TEST': '测试',
            'DOC': '文档编写',
            'STYLE': '代码规范优化'
        }

        for ctype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            type_name = type_mapping.get(ctype, ctype)
            achievements.append(f"完成 {count} 个{type_name}任务")

        # 主要贡献：基于项目配置和项目名称智能生成
        contributions = []
        project_name = project_config.get('name', '')
        project_desc = project_config.get('description', '')

        # 根据项目名称和描述智能生成
        if '俄罗斯短剧' in project_name or 'Russian' in project_name:
            # 俄罗斯短剧项目：内容分发平台
            if '内容分发' in project_desc or '分发' in project_desc:
                contributions.append("内容分发模块：支持内容分发功能")
            if '用户会员' in project_desc or '订阅' in project_desc:
                contributions.append("用户订阅模块：实现用户会员订阅管理功能")
            if '剧集管理' in project_desc:
                contributions.append("剧集管理模块：支持剧集上传和管理")
            if '支付集成' in project_desc:
                contributions.append("支付集成：对接第三方支付接口")
        elif '全球收单' in project_name or '收单' in project_name:
            # 全球收单项目：跨境支付
            contributions.append("支付通道模块：对接多个支付渠道")
            contributions.append("收单结算模块：处理跨境支付和结算")
            contributions.append("清结算模块：处理代付和清结算业务")
        elif '引流权益兑换' in project_name or 'exc' in project_name:
            # 引流权益兑换项目
            if '广告' in project_desc or '引流' in project_desc:
                contributions.append("流量通道模块：广告投放和引流功能")
            contributions.append("支付通道模块：对接多个支付渠道")
            contributions.append("商户管理功能：支持商户入驻和配置")
        elif 'ChatPPT' in project_name:
            # ChatPPT 项目
            contributions.append("内容生成模块：基于 LLM 的 PPT 内容生成")
            contributions.append("多模态输入：支持文本、语音和图像输入")
            contributions.append("工作流管理：Chatbot 和 Review Agent 协作")
        else:
            # 通用逻辑
            has_ad = any(word in project_desc for word in ['广告', '引流', '流量'])
            has_payment = any(word in project_desc for word in ['支付', '订单', '退款', '结算'])
            if has_ad:
                contributions.append("流量通道模块：广告投放和引流功能")
            if has_payment:
                contributions.append("支付通道模块：对接支付渠道和处理订单")
            if '缓存' in project_desc or 'Redis' in project_config.get('tech_stack', []):
                contributions.append("缓存机制：使用Redis提升性能")
            if '商户' in project_desc or '用户' in project_desc:
                contributions.append("商户管理功能：支持商户入驻和配置")

        # 如果没有生成任何贡献，添加默认值
        if not contributions:
            contributions = [f"参与 {project_config['name']} 项目开发"]

        return ProjectSummary(
            project_id=project_config["id"],
            description=description,
            technical_highlights=tech_highlights,
            key_achievements=achievements,
            main_contributions=contributions
        )
