"""简历生成服务入口"""
import logging
from typing import List, Optional, Dict
from pathlib import Path

from src.core.git.commit_fetcher import CommitFetcher
from src.core.git.commit_splitter import CommitSplitter
from src.core.git.task_classifier import TaskClassifier, CommitFilter
from src.core.git.commit_aggregator import CommitAggregator
from src.core.git.repo import GitRepoService
from src.core.agents.project_summarizer import ProjectSummarizerAgent
from src.core.agents.bullet_generator import BulletGeneratorAgent
from src.core.agents.company_summarizer import CompanySummarizerAgent
from .config_loader import ConfigLoader
from .document_builder import DocumentBuilder
from ..company.company_service import CompanyService

logger = logging.getLogger(__name__)


class ResumeService:
    """简历生成服务

    工作流:
    1. 获取所有项目的 commits（全量，不限时间）
    2. 过滤 -> 分类 -> 拆分 -> 聚合
    3. 项目总结（压缩信息）
    4. Bullet 生成
    5. Word 文档构建
    """

    def __init__(self, config):
        """
        Args:
            config: 配置对象（需要实现 get_author, get_llm_config, get_output_dir 等方法）
        """
        self.config = config
        self.config_loader = ConfigLoader()

        # Git 工作流组件
        self.fetcher = CommitFetcher()
        self.filter = CommitFilter()
        self.classifier = TaskClassifier()
        self.splitter = CommitSplitter()
        self.aggregator = CommitAggregator()

        # Resume 特定组件
        self.summarizer = ProjectSummarizerAgent()
        self.bullet_generator = BulletGeneratorAgent()
        self.company_summarizer = CompanySummarizerAgent()
        self.company_service = CompanyService()
        self.git_service = GitRepoService()
        self.doc_builder = DocumentBuilder(config)

        # LLM 客户端（用于拆分）
        self.llm_client = self._create_llm_client()

    def _create_llm_client(self):
        """创建 LLM 客户端"""
        from src.core.llm.client import get_llm_client
        return get_llm_client()

    def get_available_projects(self) -> List[Dict]:
        """获取可用项目列表（用于 UI）"""
        projects = self.config_loader.get_projects()
        return [{"id": p.get("id"), "name": p.get("name")} for p in projects]

    def generate_resume(self, project_ids: List[str]) -> tuple[str, Optional[Path]]:
        """生成简历

        Args:
            project_ids: 项目 ID 列表

        Returns:
            (成功消息, 文件路径)
        """
        logger = logging.getLogger(__name__)

        # 获取选中的项目配置
        all_projects = self.config_loader.get_projects()
        selected_projects = [p for p in all_projects if p.get("id") in project_ids]

        if not selected_projects:
            return "请至少选择一个项目", None

        logger.info(f">>> [简历生成] 开始处理 {len(selected_projects)} 个项目")

        resume_projects = []
        calculated_periods = {}  # 存储计算出的项目时间，用于反向填充

        for project in selected_projects:
            logger.info(f">>> [简历生成] 处理项目: {project.get('name')}")

            # 1. 并行获取所有 sources 的 commits（全量）
            all_commits = []
            for source in project.get("sources", []):
                # 优先使用项目级别的作者，否则使用全局配置的作者
                project_author = project.get("author") or self.config.get_author()
                commits = self.fetcher.fetch(
                    repo_path=self.config.to_container_path(source.get("path")),
                    branch=source.get("branch", "main"),
                    author=project_author
                    # 不传 days，获取全部 commits
                )
                logger.info(f">>> [简历生成] 源 {source.get('path')}: 获取 {len(commits)} 条 commits")
                all_commits.extend(commits)

            logger.info(f">>> [简历生成] 项目 {project.get('name')}: 总计获取 {len(all_commits)} 条 commits")

            if not all_commits:
                logger.warning(f">>> [简历生成] 项目 {project.get('name')}: 没有提交记录")
                continue

            # 计算项目时间范围（从 commits 中提取）
            period = self._calculate_project_period(all_commits, project)
            logger.info(f">>> [简历生成] 项目时间范围: {period}")

            # 保存 period 以便反向填充
            calculated_periods[project.get("id")] = period

            # 2. 过滤
            filtered_commits, filter_stats = self.filter.filter_commits(all_commits)
            logger.info(f">>> [简历生成] 过滤: {len(all_commits)} -> {len(filtered_commits)}")

            # 3. 分类
            classified_commits = self.classifier.classify_commits(filtered_commits)

            # 4. 拆分
            split_commits = self.splitter.split_commits(classified_commits, self.llm_client)

            # 5. 聚合
            aggregated_commits = self.aggregator.aggregate(split_commits, project.get("id"))

            # 6. 项目总结（压缩信息）
            summary = self.summarizer.summarize(aggregated_commits, project)

            # 7. 获取 claude.md / readme（优先使用 primary 源）
            primary_source = None
            for source in project.get("sources", []):
                if source.get("primary"):
                    primary_source = source
                    break
            # 如果没有 primary，使用第一个
            if not primary_source and project.get("sources"):
                primary_source = project.get("sources")[0]

            git_ctx = self.git_service.get_context(
                path=self.config.to_container_path(primary_source.get("path", "")) if primary_source else "",
                branch=primary_source.get("branch", "main") if primary_source else "main"
            )
            logger.info(f">>> [简历生成] Git context 来源: {primary_source.get('path') if primary_source else 'None'}")

            # 8. 生成 bullets
            bullets = self.bullet_generator.generate(
                summary=summary,
                claude_md=git_ctx.claude_md,
                readme=git_ctx.readme
            )

            resume_projects.append({
                "name": project.get("name"),
                "period": period,
                "description": summary.description,
                "main_contributions": summary.main_contributions,
                "tech_stack": ", ".join(project.get("tech_stack", [])),
                "bullets": bullets,
                "highlights": project.get("highlights", [])
            })

        # 9. 生成 Word
        if not resume_projects:
            return "没有找到有效的项目数据", None

        filepath = self.doc_builder.build(resume_projects)

        # 反向填充 period 到配置文件
        if calculated_periods:
            self._update_periods_in_config(calculated_periods)

        return f"✅ 简历生成成功！共 {len(resume_projects)} 个项目", filepath

    def generate_resume_with_template(self, project_ids: List[str], template_path: str) -> tuple[str, Optional[Path]]:
        """基于历史简历模板生成新简历（支持公司工作经历）

        Args:
            project_ids: 要添加的项目 ID 列表
            template_path: 历史简历文件路径

        Returns:
            (成功消息, 文件路径)
        """
        logger = logging.getLogger(__name__)

        # 获取选中的项目配置
        all_projects = self.config_loader.get_projects()
        selected_projects = [p for p in all_projects if p.get("id") in project_ids]

        if not selected_projects:
            return "请至少选择一个项目", None

        logger.info(f">>> [简历生成] 基于模板，添加 {len(selected_projects)} 个新项目")
        for p in selected_projects:
            logger.info(f">>> [简历生成] 选中项目: {p.get('name')}, company_id: {p.get('company_id')!r}")

        # 第一步：并发处理多个项目，每个项目完全独立
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        resume_projects = []
        calculated_periods = {}
        project_data_map = {}  # 存储项目完整数据，用于公司工作经历生成
        lock = threading.Lock()

        def process_single_project(project, idx):
            """处理单个项目（线程安全）"""
            project_name = project.get('name')
            logger.info(f">>> [简历生成] [线程{idx}] 开始处理项目: {project_name}")

            try:
                # 获取所有源的 commits
                all_commits = []
                for source_idx, source in enumerate(project.get("sources", [])):
                    project_author = project.get("author") or self.config.get_author()
                    commits = self.fetcher.fetch(
                        repo_path=self.config.to_container_path(source.get("path")),
                        branch=source.get("branch", "main"),
                        author=project_author
                    )
                    logger.info(f">>> [简历生成] [线程{idx}] 源 {source.get('path')}: 获取 {len(commits)} 条 commits")
                    all_commits.extend(commits)

                if not all_commits:
                    logger.warning(f">>> [简历生成] [线程{idx}] 项目 {project_name}: 没有提交记录")
                    return None

                # 计算项目时间范围
                period = self._calculate_project_period(all_commits, project)

                # ====== 路由：有 modules 走新流程，否则走旧流程 ======
                if project.get("modules"):
                    logger.info(f">>> [简历生成] [线程{idx}] 使用新流程（模块分类）: {project_name}")
                    project_data = self._process_with_modules(all_commits, project, period, idx)
                else:
                    logger.info(f">>> [简历生成] [线程{idx}] 使用旧流程（LLM总结）: {project_name}")
                    project_data = self._process_with_llm(all_commits, project, period, idx)

                if not project_data:
                    return None

                logger.info(f">>> [简历生成] [线程{idx}] 完成项目: {project_name}")
                return {
                    "project_data": project_data,
                    "project_id": project.get("id"),
                    "period": period
                }
            except Exception as e:
                logger.error(f">>> [简历生成] [线程{idx}] 处理项目 {project_name} 失败: {e}")
                return None

        # 使用线程池并发处理项目
        with ThreadPoolExecutor(max_workers=min(len(selected_projects), 3)) as executor:
            # 提交所有任务，保持原始顺序
            future_to_idx = {
                executor.submit(process_single_project, project, idx): idx
                for idx, project in enumerate(selected_projects)
            }

            # 按照原始顺序收集结果
            results = [None] * len(selected_projects)
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                result = future.result()
                results[idx] = result

            # 按照原始顺序添加到结果列表
            for result in results:
                if result:
                    resume_projects.append(result["project_data"])
                    calculated_periods[result["project_id"]] = result["period"]
                    project_data_map[result["project_id"]] = result["project_data"]

        if not resume_projects:
            return "没有找到有效的项目数据", None

        # 第二步：按公司分组，生成工作经历（只传递属于该公司的项目）
        work_experiences = self._generate_work_experiences(resume_projects)

        # 第三步：基于模板生成（插入工作经历 + 项目经验）
        filepath = self.doc_builder.build_with_template(
            new_projects=resume_projects,
            work_experiences=work_experiences,
            template_path=template_path
        )

        # 反向填充 period 到配置文件
        if calculated_periods:
            self._update_periods_in_config(calculated_periods)

        return f"✅ 简历生成成功！{len(work_experiences)} 个公司经历 + {len(resume_projects)} 个项目", filepath

    # ---- 项目处理方法 ----

    def _process_with_modules(self, all_commits: list, project: dict, period: str, idx: int) -> dict:
        """新流程：使用 ResumeGenerationWorkflow（模块分类）"""
        from src.core.workflow.resume_graph import ResumeGenerationWorkflow

        workflow = ResumeGenerationWorkflow()
        result = workflow.run(all_commits, project)

        if not result:
            logger.warning(f">>> [简历生成] [线程{idx}] 新流程无结果，使用 config fallback")
            result = self._generate_from_config_fallback(project)

        return {
            "id": project.get("id"),
            "name": project.get("name"),
            "period": period,
            "description": result.get("description", project.get("description", "")),
            "main_contributions": result.get("main_contributions", []),
            "key_achievements": result.get("key_achievements", []),
            "tech_stack": ", ".join(project.get("tech_stack", [])),
            "bullets": result.get("key_achievements", []),
            "highlights": project.get("highlights", []),
            "company_id": project.get("company_id")
        }

    def _process_with_llm(self, all_commits: list, project: dict, period: str, idx: int) -> dict:
        """旧流程：LLM 自由总结（无 modules 配置时使用）"""
        from src.core.agents.project_summarizer import ProjectSummarizerAgent
        from src.core.agents.bullet_generator import BulletGeneratorAgent

        project_summarizer = ProjectSummarizerAgent()
        bullet_generator = BulletGeneratorAgent()

        filtered_commits, filter_stats = self.filter.filter_commits(all_commits)
        classified_commits = self.classifier.classify_commits(filtered_commits)
        split_commits = self.splitter.split_commits(classified_commits, self.llm_client)
        aggregated_commits = self.aggregator.aggregate(split_commits, project.get("id"))

        summary = project_summarizer.summarize(aggregated_commits, project)

        # 优先使用 primary 源获取 Git context
        primary_source = None
        for source in project.get("sources", []):
            if source.get("primary"):
                primary_source = source
                break
        if not primary_source and project.get("sources"):
            primary_source = project.get("sources")[0]

        git_ctx = self.git_service.get_context(
            path=primary_source.get("path", "") if primary_source else "",
            branch=primary_source.get("branch", "main") if primary_source else "main"
        )

        bullets = bullet_generator.generate(
            summary=summary,
            claude_md=git_ctx.claude_md,
            readme=git_ctx.readme
        )

        return {
            "id": project.get("id"),
            "name": project.get("name"),
            "period": period,
            "description": summary.description,
            "main_contributions": summary.main_contributions,
            "key_achievements": summary.key_achievements,
            "tech_stack": ", ".join(project.get("tech_stack", [])),
            "bullets": bullets,
            "highlights": project.get("highlights", []),
            "company_id": project.get("company_id")
        }

    def _generate_from_config_fallback(self, project: dict) -> dict:
        """Fallback：直接用 config 生成（不调用 LLM）

        根据模块名称生成多样化的描述，避免重复"相关功能开发和维护"
        """
        modules = project.get("modules", [])
        description = project.get("description", "")
        project_name = project.get("name", "")

        # 根据模块名称和关键词生成多样化的描述
        def generate_contribution(module: dict) -> str:
            """根据模块生成贡献描述"""
            name = module["name"]
            keywords = module.get("keywords", [])

            # 根据关键词选择合适的动词和描述
            if any(kw in keywords for kw in ["支付", "pay", "订单", "交易"]):
                return f"{name}：负责支付流程和订单管理功能"
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
                return f"{name}：对接支付渠道实现收单功能"
            elif any(kw in keywords for kw in ["换汇", "exchange", "汇率", "currency"]):
                return f"{name}：支持实时换汇和汇率管理"
            elif any(kw in keywords for kw in ["代付", "payout"]):
                return f"{name}：实现代付审核和批量代付功能"
            elif any(kw in keywords for kw in ["清结算", "settlement", "清算"]):
                return f"{name}：完成清结算和对账功能开发"
            elif any(kw in keywords for kw in ["剧集", "drama", "episode", "内容管理"]):
                return f"{name}：负责剧集管理和内容发布功能"
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

    def _generate_work_experiences(self, resume_projects: List[Dict]) -> List[Dict]:
        """生成公司工作经历

        Args:
            resume_projects: 项目列表（包含 company_id）

        Returns:
            工作经历列表 [{company_info, work_experience, company_period}]
        """
        logger = logging.getLogger(__name__)
        work_experiences = []

        # 按公司分组
        company_groups = {}
        personal_projects = []  # 无公司的项目

        for project in resume_projects:
            company_id = project.get("company_id")
            logger.info(f">>> [简历生成] 项目: {project.get('name')}, company_id: {company_id!r}, type: {type(company_id)}")
            if company_id:
                if company_id not in company_groups:
                    company_groups[company_id] = []
                company_groups[company_id].append(project)
            else:
                personal_projects.append(project)

        # 为每个公司生成工作经历（每个公司独立处理，避免上下文污染）
        for company_id, projects in company_groups.items():
            company_info = self.company_service.get_company_by_id(company_id)
            if not company_info:
                logger.warning(f">>> [简历生成] 公司不存在: {company_id}")
                continue
            company_period = ""

            logger.info(f">>> [简历生成] 处理公司: {company_info['name']}, 项目数: {len(projects)}")
            for p in projects:
                logger.info(f">>> [简历生成]   - {p['name']}")

            # 每次创建新的 agent 实例，确保没有历史上下文
            from src.core.agents.company_summarizer import CompanySummarizerAgent
            company_summarizer = CompanySummarizerAgent()

            # 计算公司时间范围（从项目中取最早和最晚）
            periods = [p.get("period", "") for p in projects if p.get("period")]
            if periods:
                # 提取开始时间和结束时间（完整格式：YYYY/M）
                start_periods = []
                end_periods = []
                for period in periods:
                    try:
                        parts = period.split("—")
                        if len(parts) == 2:
                            start_part = parts[0].strip()  # 格式：YYYY/M
                            end_part = parts[1].strip()    # 格式：YYYY/M 或 "至今"
                            start_periods.append(start_part)
                            if "至今" in end_part:
                                end_periods.append("至今")
                            else:
                                end_periods.append(end_part)
                    except (ValueError, IndexError):
                        pass

                if start_periods:
                    # 找最早的开始时间（按年月排序）
                    start_periods.sort()
                    company_start = start_periods[0]

                    if end_periods:
                        # 检查是否有"至今"
                        if "至今" in end_periods:
                            company_end = "至今"
                        else:
                            # 找最晚的结束时间
                            end_periods.sort()
                            company_end = end_periods[-1]
                        company_period = f"{company_start}—{company_end}"
                    else:
                        company_period = f"{company_start}—至今"
                else:
                    company_period = ""

            logger.info(f">>> [简历生成] 公司: {company_info['name']}, 时间: {company_period}")

            # 只传递属于该公司的项目给 agent
            work_experience = company_summarizer.generate_work_experience(
                company_info=company_info,
                projects=projects
            )

            work_experiences.append({
                "company_info": company_info,
                "work_experience": work_experience,
                "company_period": company_period,
                "projects": [p["id"] for p in projects]
            })

            work_exp_lines = len(work_experience.split('\n')) if work_experience else 0
            logger.info(f">>> [简历生成] 生成工作经历: {company_info['name']}, {work_exp_lines} 行")
            logger.info(f">>> [简历生成] 完成公司: {company_info['name']}")

        logger.info(f">>> [简历生成] 总计 {len(work_experiences)} 个公司经历, {len(personal_projects)} 个个人项目")
        logger.info(f">>> [简历生成] 公司分组: {list(company_groups.keys())}")

        return work_experiences

    def _calculate_project_period(self, commits: List[Dict], project: Dict) -> str:
        """从 commits 计算项目时间范围

        Args:
            commits: 项目所有 commits
            project: 项目配置

        Returns:
            格式化的时间范围，如 "2023/06—2024/03" 或 "2024/05—至今"
        """
        from datetime import datetime

        # 如果配置中指定了 period，直接使用
        if project.get("period"):
            return project["period"]

        if not commits:
            return ""

        # 提取所有 commit 日期
        dates = [commit["date"] for commit in commits if commit.get("date")]

        if not dates:
            return ""

        # 排序找到最早和最晚
        dates.sort()
        start_date = dates[0]
        end_date = dates[-1]

        # 检查是否还在进行中（最近1个月有提交）
        # 处理时区问题：将所有日期转为 naive datetime 进行比较
        from datetime import timedelta

        def make_naive(dt):
            """将 aware datetime 转为 naive"""
            if dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            return dt

        start_date = make_naive(start_date)
        end_date = make_naive(end_date)
        now = datetime.now()

        # 更简单的判断：如果最晚提交在最近30天内，显示"至今"
        is_ongoing = (now - end_date).days <= 30

        # 格式化：YYYY/M—YYYY/M 或 YYYY/M—至今
        start_str = f"{start_date.year}/{start_date.month}"
        if is_ongoing:
            end_str = "至今"
        else:
            end_str = f"{end_date.year}/{end_date.month}"

        period = f"{start_str}—{end_str}"
        logger.info(f">>> [简历生成] 项目时间计算: {len(dates)} 条提交, 范围 {start_str} 到 {end_str}, 进行中={is_ongoing}")

        return period

    def _update_periods_in_config(self, periods: Dict[str, str]):
        """将计算出的项目时间反向填充到配置文件

        Args:
            periods: {project_id: period} 字典
        """
        import json
        from pathlib import Path

        config_path = Path("config/projects.json")
        if not config_path.exists():
            logger.warning(f">>> [简历生成] 配置文件不存在: {config_path}")
            return

        try:
            # 读取配置
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 更新 period
            updated_count = 0
            for project in data.get('projects', []):
                project_id = project.get('id')
                if project_id in periods:
                    project['period'] = periods[project_id]
                    updated_count += 1
                    logger.info(f">>> [简历生成] 更新项目时间: {project.get('name')} -> {periods[project_id]}")

            # 保存配置
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f">>> [简历生成] 已反向填充 {updated_count} 个项目时间到配置文件")

        except Exception as e:
            logger.error(f">>> [简历生成] 反向填充项目时间失败: {e}")

    def _load_extra_docs(self, project: Dict) -> str:
        """加载项目的额外文档"""
        # 优先使用新的 docs 字段（相对路径），兼容旧的 extra_docs
        docs = project.get("docs", []) or project.get("extra_docs", [])
        if not docs:
            return ""

        content_parts = []
        docs_base_dir = Path("config/docs")

        for doc_rel_path in docs:
            try:
                # 新格式：相对路径如 "exc/CLAUDE.md"
                # 旧格式：可能是绝对路径
                doc_path = Path(doc_rel_path)
                if not doc_path.is_absolute():
                    doc_path = docs_base_dir / doc_rel_path

                if doc_path.exists():
                    text = doc_path.read_text(encoding='utf-8')
                    content_parts.append(f"## {doc_path.name}\n{text[:1000]}")  # 增加到1000字符
                    logger.info(f">>> [简历生成] 加载文档: {doc_path.name}, {len(text)} 字符")
                else:
                    logger.warning(f">>> [简历生成] 文档不存在: {doc_path}")
            except Exception as e:
                logger.warning(f">>> [简历生成] 无法读取文档 {doc_rel_path}: {e}")

        return "\n\n".join(content_parts)
