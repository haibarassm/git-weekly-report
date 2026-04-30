"""测试完整简历生成流程"""
import sys
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

logger = logging.getLogger(__name__)

from src.integrations.resume.config_loader import ConfigLoader
from src.integrations.company.company_service import CompanyService
from src.core.git.commit_fetcher import CommitFetcher
from src.core.git.task_classifier import CommitFilter
from src.core.git.commit_splitter import CommitSplitter
from src.core.git.commit_aggregator import CommitAggregator
from src.core.workflow.resume_graph import ResumeGenerationWorkflow
from src.core.llm.client import get_llm_client

config_loader = ConfigLoader()
company_service = CompanyService()
fetcher = CommitFetcher()
filter_commits = CommitFilter.filter_commits_for_resume
splitter = CommitSplitter()
aggregator = CommitAggregator()
llm_client = get_llm_client()

# 获取所有项目
projects = config_loader.get_projects()

# 只处理杭州碰呗的项目
pengbei_projects = [p for p in projects if p.get("company_id") == "pengbei"]

print(f"杭州碰呗项目数: {len(pengbei_projects)}")
for p in pengbei_projects:
    print(f"  - {p['name']}")

# 测试每个项目
resume_projects = []
for project in pengbei_projects[:1]:  # 只测试第一个项目
    print(f"\n处理项目: {project['name']}")

    # 获取 commits
    all_commits = []
    for source in project.get("sources", []):
        commits = fetcher.fetch(
            repo_path=source.get("path"),
            branch=source.get("branch", "main"),
            author="caihong"
        )
        print(f"  {source.get('path')}: {len(commits)} 条 commits")
        all_commits.extend(commits)

    if not all_commits:
        print("  没有 commits，跳过")
        continue

    # 使用新流程
    if project.get("modules"):
        print(f"  使用新流程（模块分类）")
        workflow = ResumeGenerationWorkflow()
        result = workflow.run(all_commits, project)
        print(f"  结果: {result}")

        resume_projects.append({
            "id": project.get("id"),
            "name": project.get("name"),
            "period": project.get("period", ""),
            "company_id": project.get("company_id"),
            **result
        })

print(f"\n生成的项目数: {len(resume_projects)}")

# 测试工作经历生成
if resume_projects:
    from src.integrations.resume.resume_service import ResumeService
    from config import config

    resume_service = ResumeService(config)
    work_experiences = resume_service._generate_work_experiences(resume_projects)

    print(f"\n工作经历数: {len(work_experiences)}")
    for we in work_experiences:
        print(f"  公司: {we['company_info']['name']}")
        print(f"  时间: {we['company_period']}")
        print(f"  内容: {we['work_experience'][:100]}...")
