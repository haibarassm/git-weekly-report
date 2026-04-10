"""简历生成 Tab - 增强版：支持上传历史简历"""
import gradio as gr
from pathlib import Path
from integrations.resume.resume_service import ResumeService
from integrations.resume.resume_parser import ResumeParser


def create_resume_generate_tab(config):
    """创建简历生成 Tab - 增强版"""
    service = ResumeService(config)

    with gr.Row():
        # 左列：项目选择 + 历史简历上传
        with gr.Column(scale=1):
            gr.Markdown("### 1️⃣ 选择项目")

            projects = service.get_available_projects()
            project_choices = {f"{p['name']} ({p['id']})": p['id'] for p in projects}

            selected_projects = gr.CheckboxGroup(
                label="要包含的项目",
                choices=list(project_choices.keys()),
                value=[f"{p['name']} ({p['id']})" for p in projects[:2]]
            )

            gr.Markdown("---")
            gr.Markdown("### 2️⃣ 历史简历（可选）")

            upload_mode = gr.Radio(
                label="简历模式",
                choices=["从头生成", "基于历史简历"],
                value="从头生成"
            )

            resume_file = gr.File(
                label="上传历史简历 (Word)",
                file_types=[".docx"],
                visible=False
            )

            resume_preview = gr.Textbox(
                label="历史简历内容预览",
                lines=10,
                visible=False,
                interactive=False
            )

            gr.Markdown("---")
            gr.Markdown("### 3️⃣ 生成")

            generate_btn = gr.Button("📄 生成简历", variant="primary", size="lg")

            gr.Markdown("""
            **使用流程**
            1. 选择要包含的项目
            2. （可选）上传历史简历，在其基础上添加新项目
            3. 点击生成按钮
            4. 下载 Word 文档
            """)

        # 右列：输出
        with gr.Column(scale=2):
            gr.Markdown("### 生成结果")

            status = gr.Textbox(label="状态", lines=3)
            download_file = gr.File(label="下载简历")

    # 隐藏状态
    parsed_resume_state = gr.State({})  # 存储解析后的历史简历

    # 事件处理
    def _on_upload_mode_change(mode):
        """上传模式变化"""
        if mode == "基于历史简历":
            return gr.update(visible=True), gr.update(visible=True)
        return gr.update(visible=False), gr.update(visible=False)

    def _on_resume_upload(file):
        """处理简历上传"""
        if not file:
            return "请上传简历文件", {}

        try:
            parser = ResumeParser()
            parsed = parser.parse(file.name)

            # 生成预览文本
            preview = _generate_preview(parsed)

            return f"✅ 已解析简历: {parsed.get('personal_info', {}).get('name', '未知')}", parsed, preview
        except Exception as e:
            return f"❌ 解析失败: {str(e)}", {}, f"解析失败: {str(e)}"

    def _generate_preview(parsed):
        """生成简历预览"""
        lines = []
        lines.append("=== 个人信息 ===")
        info = parsed.get('personal_info', {})
        if info.get('name'):
            lines.append(f"姓名: {info['name']}")
        if info.get('email'):
            lines.append(f"邮箱: {info['email']}")
        if info.get('phone'):
            lines.append(f"电话: {info['phone']}")

        lines.append("\n=== 项目经验 ===")
        for project in parsed.get('projects', []):
            lines.append(f"\n【{project.get('name', '未知项目')}】")
            if project.get('tech_stack'):
                lines.append(f"技术栈: {project['tech_stack']}")
            for bullet in project.get('bullets', [])[:5]:
                lines.append(f"  - {bullet}")

        return "\n".join(lines)

    def _on_generate(project_names, mode, resume_file_path, parsed_resume):
        """生成简历"""
        if not project_names:
            return "请至少选择一个项目", None

        # 解析项目 ID
        projects = service.get_available_projects()
        project_choices = {f"{p['name']} ({p['id']})": p['id'] for p in projects}
        project_ids = [project_choices[name] for name in project_names]

        try:
            if mode == "基于历史简历" and parsed_resume:
                # 基于历史简历生成
                msg, filepath = service.generate_resume_with_template(
                    project_ids=project_ids,
                    template_data=parsed_resume
                )
            else:
                # 从头生成
                msg, filepath = service.generate_resume(project_ids)

            return msg, str(filepath) if filepath else None
        except Exception as e:
            import logging
            logging.exception("简历生成失败")
            return f"生成失败: {str(e)}", None

    # 绑定事件
    upload_mode.change(
        fn=_on_upload_mode_change,
        inputs=[upload_mode],
        outputs=[resume_file, resume_preview]
    )

    resume_file.upload(
        fn=_on_resume_upload,
        inputs=[resume_file],
        outputs=[status, parsed_resume_state, resume_preview]
    )

    generate_btn.click(
        fn=_on_generate,
        inputs=[selected_projects, upload_mode, resume_file, parsed_resume_state],
        outputs=[status, download_file]
    )
