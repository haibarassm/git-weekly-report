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
from .config_loader import ConfigLoader
from .document_builder import DocumentBuilder


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

        for project in selected_projects:
            logger.info(f">>> [简历生成] 处理项目: {project.get('name')}")

            # 1. 并行获取所有 sources 的 commits（全量）
            all_commits = []
            for source in project.get("sources", []):
                commits = self.fetcher.fetch(
                    repo_path=source.get("path"),
                    branch=source.get("branch", "main"),
                    author=self.config.get_author()
                    # 不传 days，获取全部 commits
                )
                all_commits.extend(commits)

            logger.info(f">>> [简历生成] 项目 {project.get('name')}: 获取 {len(all_commits)} 条 commits")

            if not all_commits:
                logger.warning(f">>> [简历生成] 项目 {project.get('name')}: 没有提交记录")
                continue

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

            # 7. 获取 claude.md / readme
            git_ctx = self.git_service.get_context(
                path=project.get("sources", [{}])[0].get("path", ""),
                branch=project.get("sources", [{}])[0].get("branch", "main")
            )

            # 8. 生成 bullets
            bullets = self.bullet_generator.generate(
                summary=summary,
                claude_md=git_ctx.claude_md,
                readme=git_ctx.readme
            )

            resume_projects.append({
                "name": project.get("name"),
                "tech_stack": ", ".join(project.get("tech_stack", [])),
                "bullets": bullets,
                "highlights": project.get("highlights", [])
            })

        # 9. 生成 Word
        if not resume_projects:
            return "没有找到有效的项目数据", None

        filepath = self.doc_builder.build(resume_projects)

        return f"✅ 简历生成成功！共 {len(resume_projects)} 个项目", filepath

    def generate_resume_with_template(self, project_ids: List[str], template_data: Dict) -> tuple[str, Optional[Path]]:
        """基于历史简历模板生成新简历

        Args:
            project_ids: 要添加的项目 ID 列表
            template_data: 解析后的历史简历数据

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

        resume_projects = []

        for project in selected_projects:
            # 生成新项目的 bullets（复用现有逻辑）
            all_commits = []
            for source in project.get("sources", []):
                commits = self.fetcher.fetch(
                    repo_path=source.get("path"),
                    branch=source.get("branch", "main"),
                    author=self.config.get_author()
                )
                all_commits.extend(commits)

            if not all_commits:
                logger.warning(f">>> [简历生成] 项目 {project.get('name')}: 没有提交记录")
                continue

            filtered_commits, filter_stats = self.filter.filter_commits(all_commits)
            classified_commits = self.classifier.classify_commits(filtered_commits)
            split_commits = self.splitter.split_commits(classified_commits, self.llm_client)
            aggregated_commits = self.aggregator.aggregate(split_commits, project.get("id"))

            summary = self.summarizer.summarize(aggregated_commits, project)

            # 获取额外文档内容
            extra_context = self._load_extra_docs(project)

            git_ctx = self.git_service.get_context(
                path=project.get("sources", [{}])[0].get("path", ""),
                branch=project.get("sources", [{}])[0].get("branch", "main")
            )

            bullets = self.bullet_generator.generate(
                summary=summary,
                claude_md=git_ctx.claude_md,
                readme=git_ctx.readme
            )

            resume_projects.append({
                "name": project.get("name"),
                "tech_stack": ", ".join(project.get("tech_stack", [])),
                "bullets": bullets,
                "highlights": project.get("highlights", [])
            })

        if not resume_projects:
            return "没有找到有效的项目数据", None

        # 基于模板生成
        filepath = self.doc_builder.build_with_template(resume_projects, template_data)

        return f"✅ 简历生成成功！原有项目 + {len(resume_projects)} 个新项目", filepath

    def _load_extra_docs(self, project: Dict) -> str:
        """加载项目的额外文档"""
        extra_docs = project.get("extra_docs", [])
        if not extra_docs:
            return ""

        content_parts = []
        for doc_path in extra_docs:
            try:
                path = Path(doc_path)
                if path.exists():
                    text = path.read_text(encoding='utf-8')
                    content_parts.append(f"## {path.name}\n{text[:500]}")
            except Exception as e:
                logger.warning(f"无法读取文档 {doc_path}: {e}")

        return "\n\n".join(content_parts)
