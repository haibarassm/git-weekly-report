"""项目管理 Tab - 增强版：支持仓库选择、分支选择、文档上传"""
import gradio as gr
import json
import logging
from pathlib import Path
from integrations.resume.config_loader import ConfigLoader
from integrations.git_report.git_utils import GitUtils

# 文档存储目录（使用绝对路径）
DOCS_BASE_DIR = Path(__file__).parent.parent.parent.parent / "config" / "docs"


def _scan_repos(base_dir: str) -> list:
    """扫描目录下的所有 Git 仓库"""
    base_path = Path(base_dir)
    if not base_path.exists():
        return []

    repos = []
    for item in base_path.rglob(".git"):
        repo_path = item.parent
        if GitUtils.validate_repo(str(repo_path)):
            relative_path = repo_path.relative_to(base_path)
            repos.append({
                "name": f"{relative_path} ({repo_path.name})",
                "path": str(repo_path)
            })
    return sorted(repos, key=lambda x: x["name"])


def _get_branches(repo_path: str) -> list:
    """获取仓库的所有分支"""
    try:
        return GitUtils.get_branches(repo_path)
    except:
        return ["main"]


def create_resume_manage_tab(config):
    """创建项目管理 Tab - 增强版"""
    loader = ConfigLoader()
    base_dir = config.get_base_dir()

    # 扫描可用仓库
    available_repos = _scan_repos(base_dir)

    # 项目列表
    projects_df = gr.Dataframe(
        label="现有项目",
        headers=["ID", "名称", "描述", "技术栈", "来源数"],
        value=loader.get_projects_dataframe(),
        interactive=False
    )

    gr.Markdown("---")

    # 项目表单
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 添加/编辑项目")

            project_id = gr.Textbox(label="项目 ID", placeholder="my-project")

            # 快捷操作按钮行
            with gr.Row():
                load_btn = gr.Button("📂 加载项目", size="sm", variant="secondary")
                delete_btn = gr.Button("🗑️ 删除项目", size="sm", variant="stop")

            project_name = gr.Textbox(label="项目名称", placeholder="我的项目")
            project_desc = gr.Textbox(label="项目描述", lines=2, placeholder="项目描述...")

            # 仓库来源选择器
            with gr.Group():
                gr.Markdown("**仓库来源**（可多个）")

                # 仓库选择
                repo_choices = {r["name"]: r["path"] for r in available_repos}
                repo_selector = gr.Dropdown(
                    label="选择仓库",
                    choices=list(repo_choices.keys()),
                    value=list(repo_choices.keys())[0] if repo_choices else None,
                    interactive=True,
                    filterable=True
                )

                # 分支选择（动态更新）
                repo_branch = gr.Dropdown(
                    label="分支",
                    choices=[],
                    value="main",
                    interactive=True,
                    multiselect=False,
                    filterable=True
                )

                add_source_btn = gr.Button("➕ 添加仓库", size="sm")

            sources_display = gr.JSON(label="已添加的仓库", value=[])

            tech_stack = gr.Textbox(
                label="技术栈（逗号分隔）",
                placeholder="Python, Go, PostgreSQL"
            )
            highlights = gr.Textbox(
                label="项目亮点（每行一条）",
                lines=3,
                placeholder="独立项目\n性能优化 30%"
            )
            notes = gr.Textbox(label="备注", lines=2)

            # 额外文档上传
            gr.Markdown("---")
            gr.Markdown("**1. 上传项目文档**（claude.md、README 等）")
            project_docs = gr.File(
                label="上传项目文档",
                file_count="multiple",
                file_types=[".txt", ".md", ".pdf", ".docx"]
            )
            with gr.Row():
                docs_display = gr.JSON(label="已上传的文档", value=[])
                clear_docs_btn = gr.Button("🗑️ 清空文档", size="sm", variant="stop")

            # 文档预览选择器
            doc_selector = gr.Dropdown(
                label="选择文档预览",
                choices=[],
                interactive=True
            )

            # 自动分析按钮
            gr.Markdown("**2. 自动填充项目信息**（基于文档分析）")
            analyze_btn = gr.Button("🪄 智能分析文档，自动填充", variant="secondary")

            # 手动输入（可编辑）
            gr.Markdown("**3. 手动编辑（自动填充后可修改）**")

            save_btn = gr.Button("💾 保存项目", variant="primary")

        with gr.Column(scale=2):
            gr.Markdown("### 操作说明")
            gr.Markdown("""
            **添加项目（推荐流程）**
            1. 填写项目 ID 和名称
            2. 从下拉列表选择仓库（自动扫描）
            3. 选择对应分支
            4. 上传项目文档（claude.md、README 等）
            5. 点击「智能分析文档，自动填充」
            6. 检查并修改自动填充的信息
            7. 点击保存

            **手动填写**
            - 如果没有文档，可以手动填写项目描述、技术栈和亮点

            **编辑项目**
            1. 输入要编辑的项目 ID
            2. 修改信息
            3. 点击保存
            """)

            # 文档预览区域
            gr.Markdown("---")
            gr.Markdown("### 文档内容预览")
            docs_preview = gr.Textbox(
                label="选中文档的内容",
                lines=10,
                interactive=False
            )

            status = gr.Textbox(label="状态", lines=2)

    # 隐藏状态
    docs_content_state = gr.State({})  # 存储文档内容 {filename: content}

    # 事件处理
    def _on_repo_change(repo_name):
        """仓库选择变化时更新分支列表"""
        if not repo_name:
            return gr.update(choices=[], value=None)

        base_dir = config.get_base_dir()
        repos = _scan_repos(base_dir)
        repo_path = next((r["path"] for r in repos if r["name"] == repo_name), None)

        if repo_path:
            branches = _get_branches(repo_path)
            return gr.update(choices=branches, value=branches[0] if branches else "main")
        return gr.update(choices=[], value=None)

    def _on_add_source(sources, repo_name, branch):
        """添加仓库来源"""
        if not repo_name or not branch:
            return sources, "❌ 请选择仓库和分支"

        base_dir = config.get_base_dir()
        repos = _scan_repos(base_dir)
        repo_path = next((r["path"] for r in repos if r["name"] == repo_name), None)

        if not repo_path:
            return sources, "❌ 仓库路径无效"

        sources = sources or []
        sources.append({"path": repo_path, "branch": branch})
        return sources, f"✅ 已添加 {len(sources)} 个仓库"

    def _on_upload_docs(docs_files, current_docs, current_content):
        """处理文档上传（支持多个文档）"""
        import logging
        logger = logging.getLogger(__name__)

        if not docs_files:
            return current_docs, current_content, "", gr.update(choices=[])

        content = dict(current_content) if current_content else {}

        # Gradio file 组件返回的是 NamedString 对象
        # docs_files 可能是单个文件或文件列表
        if isinstance(docs_files, list):
            files_list = docs_files
        else:
            files_list = [docs_files]

        # 处理新上传的文件
        new_docs = []
        for idx, file in enumerate(files_list):
            # 获取文件名（使用原始文件名而不是 temp 路径）
            if hasattr(file, 'name'):
                # Gradio 6.x: file.name 是 temp 路径，file.orig_name 是原始文件名
                orig_name = getattr(file, 'orig_name', None)
                if not orig_name:
                    # 从 temp 路径提取文件名
                    temp_path = file.name
                    orig_name = temp_path.split('\\')[-1].split('/')[-1]
                    logger.info(f"无法获取 orig_name，从 temp 路径提取: {temp_path} -> {orig_name}")
                else:
                    logger.info(f"获取到原始文件名: {orig_name}")
            else:
                orig_name = str(file)

            # 读取文档内容
            try:
                content_text = None

                # 方式1: 直接读取临时文件（最可靠）
                if hasattr(file, 'name'):
                    temp_path = file.name
                    logger.info(f"读取临时文件: {orig_name} -> {temp_path}")
                    try:
                        with open(temp_path, 'r', encoding='utf-8') as f:
                            content_text = f.read()
                        logger.info(f"文件读取成功，长度: {len(content_text)} 字符")
                    except Exception as e:
                        logger.warning(f"读取临时文件失败: {e}, 尝试其他方式")

                # 方式2: 使用 read() 方法（Gradio 某些版本可能支持）
                if content_text is None and hasattr(file, 'read'):
                    try:
                        raw_data = file.read()
                        logger.info(f"file.read() 返回: {type(raw_data)}, 长度: {len(str(raw_data))}")
                        # 检查是否是文件路径（不是实际内容）
                        raw_str = str(raw_data)
                        if len(raw_str) < 300 and '\\' in raw_str and '.gradio' in raw_str:
                            logger.warning(f"file.read() 返回的是路径而非内容，忽略")
                        elif isinstance(raw_data, bytes):
                            content_text = raw_data.decode('utf-8')
                        else:
                            content_text = raw_str
                    except Exception as e:
                        logger.warning(f"file.read() 失败: {e}")

                # 验证内容
                if content_text is None:
                    raise Exception("无法读取文件内容")

                # 检查内容是否太短（可能是路径）
                if len(content_text) < 500:
                    logger.warning(f"⚠️ 内容长度仅 {len(content_text)} 字符，可能不完整")

                # 检查是否有相同内容的文件已存在
                existing_key = None
                for key, existing_content in content.items():
                    if existing_content == content_text:
                        existing_key = key
                        logger.info(f"发现相同内容，将覆盖: {key}")
                        break

                # 决定使用的 key
                if existing_key:
                    # 内容相同，使用已存在的 key（覆盖）
                    display_name = existing_key
                    logger.info(f"覆盖已有文档: {display_name}")
                else:
                    # 内容不同，生成新的唯一 key
                    file_key = orig_name
                    counter = 1
                    while file_key in content:
                        # 尝试 "CLAUDE (2).md" 这样的格式
                        name_parts = orig_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            base, ext = name_parts
                            file_key = base + " (" + str(counter) + ")." + ext
                        else:
                            file_key = orig_name + " (" + str(counter) + ")"
                        counter += 1
                    display_name = file_key

                new_docs.append(display_name)

                # 存储内容
                content[display_name] = content_text
                logger.info(f"✓ 文档处理完成: {orig_name} -> {display_name}, {len(content_text)} 字符")
                if content_text:
                    logger.info(f"  预览: {content_text[:100].replace(chr(10), ' ')}...")
            except Exception as e:
                logger.exception(f"读取文档失败: {orig_name}")
                # 即使失败也需要一个 key
                if 'display_name' not in locals():
                    display_name = orig_name
                content[display_name] = f"[读取失败: {str(e)}]"

        # 构建文档列表（去重，保留新上传的顺序）
        docs = list(content.keys())

        # 更新文档选择器的选项
        doc_choices = list(content.keys())

        return docs, content, f"✅ 已上传 {len(new_docs)} 个文档（共 {len(docs)} 个）", gr.update(choices=doc_choices, value=doc_choices[0] if doc_choices else None)

    def _on_preview_doc(docs_content, selected_name):
        """预览文档内容（按文件名查找）"""
        if not docs_content or not selected_name:
            return ""

        return docs_content.get(selected_name, f"未找到文档: {selected_name}")

    def _on_save(project_id, name, desc, sources, tech, high, note, docs_content):
        """保存项目"""
        logger = logging.getLogger(__name__)
        if not project_id or not name:
            return "❌ 项目 ID 和名称不能为空", loader.get_projects_dataframe()

        # 解析数据
        tech_list = [s.strip() for s in tech.split(",") if s.strip()]
        high_list = [h.strip() for h in high.split("\n") if h.strip()]

        # 保存文档到文件系统
        docs_list = []
        project_docs_dir = DOCS_BASE_DIR / project_id

        if docs_content:
            # 清空该项目的旧文档目录，重新创建
            if project_docs_dir.exists():
                import shutil
                shutil.rmtree(project_docs_dir)
                logger.info(f"已清理旧文档目录: {project_docs_dir}")
            project_docs_dir.mkdir(parents=True, exist_ok=True)

            for filename, content in docs_content.items():
                # 安全化文件名（移除路径遍历字符）
                safe_filename = filename.replace("..", "").replace("\\", "/").split("/")[-1]
                doc_path = project_docs_dir / safe_filename

                # 写入文档
                logger.info(f"写入文档: {doc_path}, 内容长度: {len(content)}")
                doc_path.write_text(content, encoding='utf-8')

                # 存储相对路径
                docs_list.append(f"{project_id}/{safe_filename}")
        else:
            # 如果没有文档内容，删除整个文档目录
            if project_docs_dir.exists():
                import shutil
                shutil.rmtree(project_docs_dir)
                logger.info(f"无文档内容，已删除文档目录: {project_docs_dir}")

        project_data = {
            "id": project_id,
            "name": name,
            "description": desc,
            "sources": sources or [],
            "tech_stack": tech_list,
            "highlights": high_list,
            "notes": note,
            "docs": docs_list  # 相对路径列表 ["exc-pay/CLAUDE.md", "exc-pay/README.md"]
        }

        # 保存配置
        data = loader.load_config()
        existing_idx = next((i for i, p in enumerate(data.get("projects", [])) if p.get("id") == project_id), None)

        if existing_idx is not None:
            data["projects"][existing_idx] = project_data
            msg = f"✅ 项目已更新: {name}"
        else:
            if "projects" not in data:
                data["projects"] = []
            data["projects"].append(project_data)
            msg = f"✅ 项目已添加: {name}"

        loader.save_config(data)

        # 刷新列表
        new_df = loader.get_projects_dataframe()

        return msg, new_df

    def _on_delete(project_id):
        """删除项目"""
        if not project_id:
            return "❌ 请输入要删除的项目 ID", loader.get_projects_dataframe()

        # 删除文档目录
        project_docs_dir = DOCS_BASE_DIR / project_id
        if project_docs_dir.exists():
            import shutil
            shutil.rmtree(project_docs_dir)

        if loader.delete_project(project_id):
            return f"✅ 项目已删除: {project_id}", loader.get_projects_dataframe()
        else:
            return f"❌ 项目不存在: {project_id}", loader.get_projects_dataframe()

    def _on_load_project(project_id):
        """加载项目到表单"""
        if not project_id:
            return "❌ 请输入要加载的项目 ID"

        data = loader.load_config()
        projects = data.get("projects", [])

        # 查找项目
        project = next((p for p in projects if p.get("id") == project_id), None)

        if not project:
            return f"❌ 项目不存在: {project_id}", loader.get_projects_dataframe()

        # 格式化数据用于表单
        sources = project.get("sources", [])
        tech_stack = project.get("tech_stack", [])
        highlights = project.get("highlights", [])

        # 仓库路径和分支 - 需要重新扫描获取选项
        base_dir = loader.config.get_base_dir() if hasattr(loader, 'config') else "C:\\Users\\sherry\\project"
        repos = _scan_repos(base_dir)
        repo_choices = [r["name"] for r in repos]
        repo_choices.sort()

        # 获取第一个仓库的分支（作为默认值）
        default_branch = "main"
        if sources and len(sources) > 0:
            first_path = sources[0].get("path", "")
            # 查找匹配的仓库并获取其分支
            for repo in repos:
                if repo["path"] == first_path:
                    branches = _get_branches(first_path)
                    if branches:
                        default_branch = branches[0]
                    break

        # 恢复文档内容（从文件系统读取）
        docs_content = {}
        docs_list = project.get("docs", [])
        doc_choices = []

        for doc_rel_path in docs_list:
            try:
                doc_path = DOCS_BASE_DIR / doc_rel_path
                if doc_path.exists():
                    filename = doc_path.name
                    content = doc_path.read_text(encoding='utf-8')
                    docs_content[filename] = content
                    doc_choices.append(filename)
            except Exception as e:
                logging.warning(f"读取文档失败: {doc_rel_path}, {e}")

        # 返回表单数据
        return (
            f"✅ 已加载项目: {project.get('name', '')}",  # status
            project.get("name", ""),  # name
            project.get("description", ""),  # description
            sources,  # sources
            ", ".join(tech_stack) if tech_stack else "",  # tech
            "\n".join(highlights) if highlights else "",  # highlights
            project.get("notes", ""),  # notes
            gr.update(choices=repo_choices, value=repo_choices[0] if repo_choices else None),  # repo_selector update
            gr.update(value=default_branch),  # repo_branch update
            docs_list,  # docs_display
            docs_content,  # docs_content_state
            gr.update(choices=doc_choices, value=doc_choices[0] if doc_choices else None),  # doc_selector update
            docs_content.get(doc_choices[0], "") if doc_choices else "",  # docs_preview
        )

    # 绑定事件
    repo_selector.change(
        fn=_on_repo_change,
        inputs=[repo_selector],
        outputs=[repo_branch]
    )

    add_source_btn.click(
        fn=_on_add_source,
        inputs=[sources_display, repo_selector, repo_branch],
        outputs=[sources_display, status]
    )

    project_docs.upload(
        fn=_on_upload_docs,
        inputs=[project_docs, docs_display, docs_content_state],
        outputs=[docs_display, docs_content_state, status, doc_selector]
    )

    # 清空文档按钮
    def _on_clear_docs():
        """清空已上传的文档"""
        return [], {}, "✅ 已清空所有文档", gr.update(choices=[]), ""

    clear_docs_btn.click(
        fn=_on_clear_docs,
        inputs=[],
        outputs=[docs_display, docs_content_state, status, doc_selector, docs_preview]
    )

    doc_selector.change(
        fn=_on_preview_doc,
        inputs=[docs_content_state, doc_selector],
        outputs=[docs_preview]
    )

    # 智能分析文档，自动填充
    def _on_analyze_docs(docs_content):
        """分析文档，自动填充项目信息"""
        if not docs_content:
            return "❌ 请先上传文档", "", ""

        try:
            from src.core.agents.document_analyzer import DocumentAnalyzerAgent
            analyzer = DocumentAnalyzerAgent()

            # 分析文档
            result = analyzer.analyze(docs_content)

            # 格式化输出
            desc = result.get("description", "")
            tech = ", ".join(result.get("tech_stack", []))
            high = "\n".join(result.get("highlights", []))

            msg = f"✅ 分析完成！\n描述: {desc[:50]}...\n技术栈: {tech}"
            return msg, desc, tech, high
        except Exception as e:
            import logging
            logging.exception("文档分析失败")
            return f"❌ 分析失败: {str(e)}", "", "", ""

    analyze_btn.click(
        fn=_on_analyze_docs,
        inputs=[docs_content_state],
        outputs=[status, project_desc, tech_stack, highlights]
    )

    save_btn.click(
        fn=_on_save,
        inputs=[project_id, project_name, project_desc, sources_display, tech_stack, highlights, notes, docs_content_state],
        outputs=[status, projects_df]
    )

    delete_btn.click(
        fn=_on_delete,
        inputs=[project_id],
        outputs=[status, projects_df]
    )

    load_btn.click(
        fn=_on_load_project,
        inputs=[project_id],
        outputs=[status, project_name, project_desc, sources_display, tech_stack, highlights, notes, repo_selector, repo_branch, docs_display, docs_content_state, doc_selector, docs_preview]
    )


# 扩展 ConfigLoader 添加 get_projects_dataframe 方法
def _get_projects_dataframe(self):
    """获取项目列表（用于 Dataframe 显示）"""
    projects = self.get_projects()
    rows = []
    for p in projects:
        rows.append([
            p.get("id", ""),
            p.get("name", ""),
            p.get("description", "")[:30] + "..." if len(p.get("description", "")) > 30 else p.get("description", ""),
            ", ".join(p.get("tech_stack", [])),
            len(p.get("sources", []))
        ])
    return rows


# 动态添加方法
ConfigLoader.get_projects_dataframe = _get_projects_dataframe
