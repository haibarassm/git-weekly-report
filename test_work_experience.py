"""测试工作经历生成"""
import sys
import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(message)s')

from src.integrations.resume.config_loader import ConfigLoader
from src.integrations.company.company_service import CompanyService
from src.core.agents.company_summarizer import CompanySummarizerAgent

config_loader = ConfigLoader()
company_service = CompanyService()

# 获取所有项目
projects = config_loader.get_projects()

# 按公司分组
company_groups = {}
for project in projects:
    company_id = project.get("company_id")
    if company_id:
        if company_id not in company_groups:
            company_groups[company_id] = []
        company_groups[company_id].append(project)

print(f"公司分组: {list(company_groups.keys())}")
print()

# 测试每个公司的工作经历生成
for company_id, project_list in company_groups.items():
    company_info = company_service.get_company_by_id(company_id)
    if not company_info:
        print(f"公司不存在: {company_id}")
        continue

    print(f"公司: {company_info['name']}")
    print(f"项目数: {len(project_list)}")
    for p in project_list:
        print(f"  - {p['name']}")

    # 模拟项目数据（使用配置中的描述）
    mock_projects = []
    for p in project_list:
        mock_projects.append({
            "name": p["name"],
            "main_contributions": [
                f"{p['name']}：相关功能开发"
            ],
            "key_achievements": []
        })

    # 生成工作经历
    agent = CompanySummarizerAgent()
    work_experience = agent.generate_work_experience(
        company_info=company_info,
        projects=mock_projects
    )

    print(f"生成的工作经历 ({len(work_experience)} 字符):")
    print(work_experience)
    print()
    print("-" * 80)
    print()
