"""简历解析器 - 解析 Word 简历"""
from pathlib import Path
from typing import Dict, List
import logging

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logging.warning("python-docx 未安装")


class ResumeParser:
    """解析 Word 简历文件"""

    def __init__(self):
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx 未安装，请运行: pip install python-docx")

    def parse(self, filepath: str) -> Dict:
        """解析简历文件

        Returns:
            {
                "personal_info": {...},
                "projects": [
                    {"name": "...", "tech_stack": "...", "bullets": [...]},
                    ...
                ]
            }
        """
        doc = Document(filepath)

        parsed = {
            "personal_info": {},
            "projects": [],
            "skills": [],
            "raw_text": []
        }

        current_project = None
        current_section = None

        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue

            # 保存原始文本
            parsed["raw_text"].append(text)

            # 检测章节
            if self._is_section_header(text):
                current_section = self._detect_section_type(text)
                continue

            # 解析个人信息
            if current_section == "personal":
                self._parse_personal_info(text, parsed["personal_info"])

            # 解析项目经验
            elif current_section == "projects":
                if self._is_project_header(text):
                    # 保存上一个项目
                    if current_project:
                        parsed["projects"].append(current_project)
                    # 开始新项目
                    current_project = {
                        "name": text,
                        "bullets": []
                    }
                elif current_project and paragraph.style.name == 'List Bullet':
                    current_project["bullets"].append(text)

        # 保存最后一个项目
        if current_project:
            parsed["projects"].append(current_project)

        return parsed

    def _is_section_header(self, text: str) -> bool:
        """判断是否是章节标题"""
        keywords = ["个人信息", "联系方式", "项目经验", "工作经历", "技能", "教育", "Personal Info", "Projects", "Skills"]
        return any(keyword in text for keyword in keywords)

    def _detect_section_type(self, text: str) -> str:
        """检测章节类型"""
        if any(kw in text for kw in ["个人信息", "联系方式", "Personal Info", "Contact"]):
            return "personal"
        elif any(kw in text for kw in ["项目经验", "工作经历", "Projects", "Experience"]):
            return "projects"
        elif any(kw in text for kw in ["技能", "Skills"]):
            return "skills"
        return "unknown"

    def _parse_personal_info(self, text: str, info: Dict):
        """解析个人信息"""
        if "@" in text:
            info["email"] = text
        elif any(c.isdigit() for c in text) and len(text) > 5:
            info["phone"] = text
        elif "mailto:" in text or "tel:" in text:
            # 清理格式
            cleaned = text.replace("mailto:", "").replace("tel:", "").strip()
            if "@" in cleaned:
                info["email"] = cleaned
            else:
                info["phone"] = cleaned
        elif not info.get("name"):
            # 假设第一行是姓名
            info["name"] = text

    def _is_project_header(self, text: str) -> bool:
        """判断是否是项目标题"""
        # 项目标题通常较长，不包含列表标记
        # 且不全是英文缩写
        if len(text) < 3:
            return False
        if text.startswith(('- ', '•', '*')):
            return False
        # 简单判断：不以动词开头的可能是标题
        verbs = ['Built', 'Designed', 'Implemented', 'Developed', 'Optimized', 'Created', 'Managed']
        return not any(text.startswith(verb) for verb in verbs)
