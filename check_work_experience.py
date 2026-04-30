"""检查工作经历内容"""
from docx import Document
from pathlib import Path
from datetime import datetime

# 找到最新的文件
output_dir = Path("C:/Users/sherry/project/naps_report_generator/output")
docx_files = list(output_dir.glob("resume_updated_*.docx"))
if not docx_files:
    print("没有找到文件")
    exit(1)

latest_file = max(docx_files, key=lambda f: f.stat().st_mtime)
print(f"检查文件: {latest_file.name}")
print("=" * 80)

doc = Document(latest_file)

# 查找工作经历部分
in_work_section = False
work_experience_content = []

for i, para in enumerate(doc.paragraphs):
    text = para.text.strip()

    # 检测章节
    if "工作经历" in text:
        in_work_section = True
        continue

    if "项目经验" in text:
        break

    if in_work_section and text:
        work_experience_content.append({
            "line": i,
            "text": text
        })

# 分析工作经历
print("\n工作经历内容分析:")
print("-" * 80)

current_company = None
current_duties = []

for item in work_experience_content:
    text = item["text"]

    if "公司名称:" in text:
        if current_company and current_duties:
            print(f"\n【{current_company}】")
            for duty in current_duties:
                print(f"  {duty}")
        current_company = text.replace("公司名称:", "").strip()
        current_duties = []
        print(f"\n>>> 公司: {current_company}")

    elif "主要职责：" in text:
        print(f"  >>> {text}")

    elif text.startswith("●"):
        current_duties.append(text)
        print(f"  {text}")

if current_company and current_duties:
    print(f"\n【{current_company}】")
    for duty in current_duties:
        print(f"  {duty}")
