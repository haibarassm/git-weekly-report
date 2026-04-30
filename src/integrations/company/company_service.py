"""公司配置管理服务"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CompanyService:
    """公司配置管理服务"""

    CONFIG_PATH = Path("config/companies.json")

    def __init__(self):
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """确保配置文件存在"""
        if not self.CONFIG_PATH.exists():
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._save_companies([])

    def get_companies(self) -> List[Dict]:
        """获取所有公司"""
        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("companies", [])
        except Exception as e:
            logger.error(f"读取公司配置失败: {e}")
            return []

    def _save_companies(self, companies: List[Dict]):
        """保存公司配置"""
        with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({"companies": companies}, f, ensure_ascii=False, indent=2)

    def add_company(self, company: Dict) -> bool:
        """添加公司"""
        companies = self.get_companies()

        # 检查ID是否已存在
        if any(c["id"] == company["id"] for c in companies):
            logger.warning(f"公司ID已存在: {company['id']}")
            return False

        companies.append(company)
        self._save_companies(companies)
        logger.info(f"添加公司: {company['name']}")
        return True

    def update_company(self, company_id: str, company: Dict) -> bool:
        """更新公司"""
        companies = self.get_companies()

        for i, c in enumerate(companies):
            if c["id"] == company_id:
                companies[i] = company
                self._save_companies(companies)
                logger.info(f"更新公司: {company['name']}")
                return True

        logger.warning(f"公司不存在: {company_id}")
        return False

    def delete_company(self, company_id: str) -> bool:
        """删除公司"""
        companies = self.get_companies()
        original_count = len(companies)

        companies = [c for c in companies if c["id"] != company_id]

        if len(companies) < original_count:
            self._save_companies(companies)
            logger.info(f"删除公司: {company_id}")
            return True

        logger.warning(f"公司不存在: {company_id}")
        return False

    def get_company_by_id(self, company_id: str) -> Optional[Dict]:
        """根据ID获取公司"""
        for company in self.get_companies():
            if company["id"] == company_id:
                return company
        return None

    def get_company_choices(self) -> List[str]:
        """获取公司选择列表（用于UI下拉框）"""
        companies = self.get_companies()
        choices = ["无公司（个人项目）"]  # 默认选项
        for c in companies:
            choices.append(f"{c['name']} ({c['id']})")
        return choices

    def parse_company_choice(self, choice: str) -> Optional[str]:
        """解析UI选择，返回公司ID"""
        if choice == "无公司（个人项目）":
            return None

        # 提取ID：格式为 "公司名称 (id)"
        if "(" in choice and choice.endswith(")"):
            return choice[choice.rfind("(") + 1:-1]

        return None
