"""Word 文档构建器 - 生成简历 Word 文档"""
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx 未安装，请运行: pip install python-docx")


class DocumentBuilder:
    """简历 Word 文档构建器"""

    def __init__(self, config):
        """
        Args:
            config: 配置对象
        """
        self.config = config
        self.output_dir = Path(config.get_output_dir())
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build(self, resume_projects: List[Dict]) -> Path:
        """构建 Word 文档

        Args:
            resume_projects: 简历项目列表，每个项目包含:
                - name: 项目名称
                - tech_stack: 技术栈
                - bullets: bullet points
                - highlights: 项目亮点

        Returns:
            生成的文件路径
        """
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx 未安装，请运行: pip install python-docx")

        logger = logging.getLogger(__name__)

        doc = Document()

        # 标题
        title = doc.add_heading('Resume', level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 元信息
        author = self.config.get_author()
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        doc.add_paragraph(f"Generated: {generated_at}")
        if author:
            doc.add_paragraph(f"Author: {author}")
        doc.add_paragraph()

        # 项目列表
        for project in resume_projects:
            doc.add_heading(project["name"], level=2)

            # 技术栈
            if project.get("tech_stack"):
                p = doc.add_paragraph()
                p.add_run("**技术栈**: ").bold = True
                p.add_run(project["tech_stack"])

            # Bullets
            for bullet in project.get("bullets", []):
                p = doc.add_paragraph(bullet, style='List Bullet')
                p.runs[0].font.size = Pt(11)

            # 亮点
            if project.get("highlights"):
                doc.add_paragraph("**项目亮点**:", style='List Bullet').runs[0].bold = True
                for highlight in project["highlights"]:
                    p = doc.add_paragraph(highlight, style='List Bullet 2')
                    p.runs[0].font.size = Pt(10)

            doc.add_paragraph()  # 空行

        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_{timestamp}.docx"
        filepath = self.output_dir / filename

        doc.save(filepath)
        logger.info(f">>> [文档构建] 保存: {filepath}")

        return filepath

    def build_with_template(self, new_projects: List[Dict], template_data: Dict) -> Path:
        """基于历史简历模板生成新文档

        Args:
            new_projects: 新生成的项目列表
            template_data: 解析后的历史简历数据

        Returns:
            生成的文件路径
        """
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx 未安装，请运行: pip install python-docx")

        logger = logging.getLogger(__name__)

        doc = Document()

        # 从模板复制个人信息
        personal_info = template_data.get("personal_info", {})
        if personal_info.get("name"):
            doc.add_heading(personal_info["name"], level=0)
            doc.add_heading('Resume', level=1)

        # 联系方式
        contact_lines = []
        if personal_info.get("email"):
            contact_lines.append(f"Email: {personal_info['email']}")
        if personal_info.get("phone"):
            contact_lines.append(f"Phone: {personal_info['phone']}")
        if contact_lines:
            doc.add_paragraph(" | ".join(contact_lines))

        doc.add_paragraph()

        # 合并项目：历史项目 + 新项目
        all_projects = []

        # 添加历史项目
        for proj in template_data.get("projects", []):
            all_projects.append({
                "name": proj["name"],
                "tech_stack": proj.get("tech_stack", ""),
                "bullets": proj.get("bullets", []),
                "highlights": [],
                "is_new": False
            })

        # 添加新项目
        for proj in new_projects:
            all_projects.append({
                "name": proj["name"],
                "tech_stack": proj.get("tech_stack", ""),
                "bullets": proj.get("bullets", []),
                "highlights": proj.get("highlights", []),
                "is_new": True
            })

        # 项目经验
        for project in all_projects:
            doc.add_heading(project["name"], level=2)

            # 标记新项目
            if project.get("is_new"):
                p = doc.add_paragraph()
                p.add_run("[新项目] ").bold = True

            # 技术栈
            if project.get("tech_stack"):
                p = doc.add_paragraph()
                p.add_run("**技术栈**: ").bold = True
                p.add_run(project["tech_stack"])

            # Bullets
            for bullet in project.get("bullets", []):
                p = doc.add_paragraph(bullet, style='List Bullet')
                p.runs[0].font.size = Pt(11)

            # 亮点（仅新项目）
            if project.get("is_new") and project.get("highlights"):
                doc.add_paragraph("**项目亮点**:", style='List Bullet').runs[0].bold = True
                for highlight in project["highlights"]:
                    p = doc.add_paragraph(highlight, style='List Bullet 2')
                    p.runs[0].font.size = Pt(10)

            doc.add_paragraph()

        # 元信息
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        doc.add_paragraph(f"\nGenerated: {generated_at}")

        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_updated_{timestamp}.docx"
        filepath = self.output_dir / filename

        doc.save(filepath)
        logger.info(f">>> [文档构建] 保存更新简历: {filepath}")

        return filepath
