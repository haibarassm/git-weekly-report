"""项目管理 Tab - 增强版：支持仓库选择、分支选择、文档上传"""
import gradio as gr
import json
import logging
from pathlib import Path
from integrations.resume.config_loader import ConfigLoader
from src.core.git import GitRepoService
from config import config

# 文档存储目录（使用绝对路径）
DOCS_BASE_DIR = Path(__file__).parent.parent.parent.parent / "config" / "docs"


def _scan_repos(base_dir: str, project_dirs: list = None) -> list:
    """扫描目录下的所有 Git 仓库"""
    base_path = Path(base_dir)
    repos = []

    # 确定要扫描的目录列表
    if project_dirs:
        scan_dirs = [Path(d) for d in project_dirs]
    else:
        # 默认扫描 base_dir 和 project 子目录
        scan_dirs = [base_path]
        project_dir = base_path / "project"
        if project_dir.exists():
            scan_dirs.append(project_dir)

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue

        for item in scan_dir.rglob(".git"):
            repo_path = item.parent
            try:
                if GitRepoService.validate_repo(str(repo_path)):
                    # 生成显示名称，包含来源目录提示
                    try:
                        relative_path = repo_path.relative_to(scan_dir)
                    except ValueError:
                        # 不在扫描目录下，使用完整路径的最后一部分
                        relative_path = repo_path.name

                    # 限制深度：只保留 2-3 级路径
                    parts = relative_path.parts
                    if len(parts) <= 3:
                        # 添加来源目录标识，帮助用户识别是 GitLab 还是 GitHub
                        dir_name = scan_dir.name
                        if "极客时间" in str(scan_dir):
                            source_label = "[GitHub] "
                        elif "project" in str(scan_dir):
                            source_label = "[GitLab] "
                        else:
                            source_label = ""

                        repos.append({
                            "name": f"{source_label}{relative_path} ({repo_path.name})",
                            "path": str(repo_path)
                        })
            except Exception as e:
                import logging
                logging.warning(f"验证仓库失败 {repo_path}: {e}")
                continue

    return sorted(repos, key=lambda x: x["name"])


def _get_branches(repo_path: str) -> list:
    """获取仓库的所有分支"""
    try:
        return GitRepoService.get_branches(repo_path)
    except:
        return ["main"]


def create_resume_manage_tab(config):
    """创建项目管理 Tab - 增强版"""
    loader = ConfigLoader()
    base_dir = config.get_base_dir()

    # 获取项目目录列表（支持多目录扫描）
    project_dirs = config.get_project_dirs()

    # 扫描可用仓库
    available_repos = _scan_repos(base_dir, project_dirs)

    # 获取项目列表
    projects = loader.get_projects()
    project_choices = [f"{p.get('id', '')} - {p.get('name', '')}" for p in projects]

    # 项目列表
    with gr.Row():
        project_selector = gr.Dropdown(
            label="选择项目查看/加载",
            choices=project_choices,
            value=None,
            interactive=True,
            filterable=True
        )
        view_btn = gr.Button("👁️ 查看详情", size="sm", variant="secondary")

    # 项目详情展示
    project_detail = gr.Markdown(
        value="*点击「查看详情」查看项目信息*",
        label="项目详情"
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
                    value=None,  # 改为 None，由事件动态设置
                    interactive=True,
                    multiselect=False,
                    filterable=True
                )

                # 主项目标记
                is_primary = gr.Checkbox(
                    label="设为主项目",
                    value=False,
                    info="文档分析时优先使用主项目的业务描述"
                )

                with gr.Row():
                    add_source_btn = gr.Button("➕ 添加仓库", size="sm")
                    clear_sources_btn = gr.Button("🗑️ 清空仓库", size="sm", variant="stop")

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
            project_author = gr.Textbox(
                label="Git 作者（用于筛选提交）",
                placeholder="your-email@example.com 或 GitHub用户名",
                info="留空则使用全局配置的作者"
            )
            git_platform = gr.Radio(
                label="Git 平台",
                choices=["GitHub", "GitLab", "Gitee", "Other"],
                value="GitHub",
                info="简历生成时使用对应的平台样式"
            )

            # 公司选择器
            from integrations.company.company_service import CompanyService
            company_service = CompanyService()
            company_choices = company_service.get_company_choices()

            company_selector = gr.Dropdown(
                label="所属公司（可选）",
                choices=company_choices,
                value="无公司（个人项目）",
                interactive=True,
                info="关联公司后，生成简历时会自动添加工作经历"
            )

            # 额外文档上传
            gr.Markdown("---")
            gr.Markdown("**1. 上传项目文档**（claude.md、README 等）")

            # 文档来源项目选择器
            doc_project_selector = gr.Dropdown(
                label="文档来源",
                choices=["自动检测", "手动指定"],
                value="自动检测",
                interactive=True,
                info="选择文档来自哪个项目（用于区分同名文件）"
            )

            # 手动指定项目选择器（初始隐藏）- 使用 Group 包装
            with gr.Group(visible=False) as manual_project_group:
                manual_project_selector = gr.Dropdown(
                    label="选择项目",
                    choices=[
                        "spjvm", "spjvm-adm",
                        "exc-pay", "exc-adm",
                        "naps-tc", "naps-oc", "naps-gateway", "naps-common", "naps-sharding",
                        "naps-ac", "naps-uc"
                    ],
                    value="spjvm",
                    interactive=True,
                    info="选择此文档所属的项目"
                )

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
        project_dirs = config.get_project_dirs()
        repos = _scan_repos(base_dir, project_dirs)
        repo_path = next((r["path"] for r in repos if r["name"] == repo_name), None)

        if repo_path:
            branches = _get_branches(repo_path)
            if not branches:
                branches = ["main"]
            return gr.update(choices=branches, value=branches[0])
        return gr.update(choices=[], value=None)

    def _on_add_source(sources, repo_name, branch, is_primary):
        """添加仓库来源"""
        if not repo_name or not branch:
            return sources, "❌ 请选择仓库和分支", False

        base_dir = config.get_base_dir()
        project_dirs = config.get_project_dirs()
        repos = _scan_repos(base_dir, project_dirs)
        repo_path = next((r["path"] for r in repos if r["name"] == repo_name), None)

        if not repo_path:
            return sources, "❌ 仓库路径无效", False

        sources = sources or []

        # 检查是否已存在相同的路径和分支
        existing_idx = next((i for i, s in enumerate(sources) if s.get("path") == repo_path and s.get("branch") == branch), None)

        if existing_idx is not None:
            # 已存在，更新主项目标记
            if is_primary:
                # 取消其他项目的主标记
                for s in sources:
                    s["primary"] = False
                sources[existing_idx]["primary"] = True
            msg = f"✅ 已更新 {repo_path.split(chr(92))[-1]} 为主项目" if is_primary else f"✅ 已更新仓库"
        else:
            # 不存在，添加新的
            # 如果设置为主项目，先取消其他项目的主标记
            if is_primary:
                for s in sources:
                    s["primary"] = False

            sources.append({"path": repo_path, "branch": branch, "primary": is_primary})
            msg = f"✅ 已添加 {repo_path.split(chr(92))[-1]}{' (主项目)' if is_primary else ''}"

        return sources, msg, False

    def _on_clear_sources():
        """清空所有仓库"""
        return [], "✅ 已清空所有仓库", False

    def _on_doc_project_change(doc_source_mode, sources):
        """文档来源选择变化"""
        if doc_source_mode == "手动指定":
            # 显示手动指定选择器的 Group
            return gr.update(visible=True)
        else:
            return gr.update(visible=False)

    def _extract_project_from_doc(content: str) -> str:
        """从文档内容中直接提取项目名称（最准确）"""
        import re
        import logging
        logger = logging.getLogger(__name__)

        # 模式1: **项目名 (描述 - This Repository)**
        # 例如: **exc-pay (投流端 - This Repository)**
        pattern1 = r'\*\*([a-zA-Z0-9\-_]+)\s*\([^)]*?\s*-\s*This\s+Repository\s*\)\*\*'
        match1 = re.search(pattern1, content)
        if match1:
            project_name = match1.group(1).lower()
            logger.info(f"从文档提取项目名称 (模式1): {project_name}")
            return project_name

        # 模式2: ## 项目概述 后面的 **项目名**
        # 例如:
        # ## 项目概述
        # **exc-adm**
        pattern2 = r'##\s*项目概述\s*\n\s*\*\*([a-zA-Z0-9\-_]+)\*\*'
        match2 = re.search(pattern2, content, re.IGNORECASE)
        if match2:
            project_name = match2.group(1).lower()
            logger.info(f"从文档提取项目名称 (模式2): {project_name}")
            return project_name

        # 模式3: ## Project Overview 后面的 **Project Name**
        pattern3 = r'##\s*Project\s+Overview\s*\n\s*\*\*([a-zA-Z0-9\-_]+)\*\*'
        match3 = re.search(pattern3, content, re.IGNORECASE)
        if match3:
            project_name = match3.group(1).lower()
            logger.info(f"从文档提取项目名称 (模式3): {project_name}")
            return project_name

        # 模式4: # 项目名 在文档开头
        pattern4 = r'^#\s+([a-zA-Z0-9\-_]+)\s*项目'
        match4 = re.search(pattern4, content, re.MULTILINE | re.IGNORECASE)
        if match4:
            project_name = match4.group(1).lower()
            logger.info(f"从文档提取项目名称 (模式4): {project_name}")
            return project_name

        return ""

    def _detect_project_prefix(content: str) -> str:
        """检测文档内容属于哪个项目，返回项目前缀"""
        import logging
        import re
        logger = logging.getLogger(__name__)

        # 优先：从文档中直接提取项目名称
        direct_extract = _extract_project_from_doc(content)
        if direct_extract:
            return direct_extract

        # 回退：使用关键词匹配（评分系统）
        content_lower = content.lower()

        # 项目特征关键词（按优先级排序，更具体的放前面）
        project_features = {
            'spjvm': {
                'keywords': ['spjvm', '短剧', 'drama', 'episode', 'video', 'playlet', 'vod'],
                'exclude': ['exc-pay', 'excpay', 'exc-adm', 'excadm']  # 排除依赖关键词
            },
            'exc-adm': {
                'keywords': ['exc-adm', 'excadm', '投流后台', '管理后台', 'admin'],
                'exclude': ['exc-pay', 'excpay']  # 排除依赖项目
            },
            'exc-pay': {
                'keywords': ['exc-pay', 'excpay', '投流端', '支付网关', 'payment gateway'],
                'exclude': ['exc-adm', 'excadm', '短剧', 'drama', 'video']
            },
            'naps-oc': {
                'keywords': ['naps-oc', 'onboard', '商户', 'merch', 'kyc', '入驻'],
                'exclude': ['naps-tc', 'transaction center']
            },
            'naps-tc': {
                'keywords': ['naps-tc', 'transaction center', '跨境支付', '收单', 'acquire'],
                'exclude': ['naps-oc', 'onboard', 'naps-gateway']
            },
            'naps-gateway': {
                'keywords': ['naps-gateway', 'gateway', '网关'],
                'exclude': []
            },
        }

        # 统计每个项目的关键词匹配次数
        project_scores = {}
        for project, config in project_features.items():
            score = 0
            for keyword in config['keywords']:
                # 统计关键词出现次数
                count = content_lower.count(keyword)
                if count > 0:
                    score += count
                    logger.info(f"项目 {project} 匹配关键词 '{keyword}': {count} 次")

            # 减去排除关键词的匹配次数（避免误判）
            for exclude_keyword in config['exclude']:
                if exclude_keyword in content_lower:
                    # 检查是否是"依赖"、"基于"等上下文
                    context_patterns = [
                        rf'基于\s+{re.escape(exclude_keyword)}',
                        rf'依赖\s+{re.escape(exclude_keyword)}',
                        rf'从\s+{re.escape(exclude_keyword)}',
                        rf'{re.escape(exclude_keyword)}\s*项目',
                        rf'{re.escape(exclude_keyword)}\s*服务',
                    ]
                    for pattern in context_patterns:
                        if re.search(pattern, content_lower):
                            score -= 2  # 发现依赖上下文，大幅降低权重
                            logger.info(f"项目 {project} 发现依赖上下文 '{exclude_keyword}'，扣分")
                            break

            if score > 0:
                project_scores[project] = score

        # 返回得分最高的项目
        if project_scores:
            best_project = max(project_scores, key=project_scores.get)
            logger.info(f"检测到项目类型: {best_project} (得分: {project_scores[best_project]})")
            return best_project

        return ""  # 未检测到明确的项目类型

    def _on_upload_docs(docs_files, current_docs, current_content, doc_source_mode, manual_project):
        """处理文档上传（支持多个文档）"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            if not docs_files:
                return current_docs, current_content, "", gr.update(choices=[])

            content = dict(current_content) if current_content else {}

            # 确定使用的前缀（手动指定优先）
            manual_prefix = None
            if doc_source_mode == "手动指定" and manual_project:
                manual_prefix = manual_project.lower()
                logger.info(f"使用手动指定的项目前缀: {manual_prefix}")

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

                # 检测文档类型并添加项目前缀
                file_key = orig_name

                # 优先使用手动指定的前缀
                # 只对纯标准文件名添加前缀，不包括已有标记的文件（如 CLAUDE-g.md）
                standard_names = ["claude.md", "readme.md", "changelog.md"]
                is_standard_name = orig_name.lower() in standard_names

                if manual_prefix and is_standard_name:
                    name_parts = orig_name.rsplit('.', 1)
                    if len(name_parts) == 2:
                        file_key = f"{manual_prefix}_{name_parts[0]}.{name_parts[1]}"
                    else:
                        file_key = f"{manual_prefix}_{orig_name}"
                    logger.info(f"使用手动指定前缀 {manual_prefix}，重命名: {orig_name} -> {file_key}")
                else:
                    # 自动检测项目类型
                    project_prefix = _detect_project_prefix(content_text)
                    # 只对标准文件名且检测到项目类型时，加上前缀
                    if project_prefix and is_standard_name:
                        name_parts = orig_name.rsplit('.', 1)
                        if len(name_parts) == 2:
                            file_key = f"{project_prefix}_{name_parts[0]}.{name_parts[1]}"
                        else:
                            file_key = f"{project_prefix}_{orig_name}"
                        logger.info(f"检测到项目类型 {project_prefix}，重命名: {orig_name} -> {file_key}")

                # 检查是否有相同内容的文件已存在
                existing_key = None
                for key, existing_content in content.items():
                    if existing_content == content_text:
                        existing_key = key
                        logger.info(f"发现相同内容，将覆盖: {key}")
                        break

                # 决定使用的 key
                if existing_key:
                    # 内容相同，如果新文件名有前缀，使用新文件名；否则使用已存在的 key
                    if file_key != orig_name:  # 文件名被修改过（添加了前缀）
                        display_name = file_key
                        logger.info(f"内容相同但使用新文件名: {display_name}")
                    else:
                        display_name = existing_key
                        logger.info(f"覆盖已有文档: {display_name}")
                else:
                    # 内容不同，检查文件名是否已存在
                    if file_key in content:
                        # 文件名已存在，添加序号
                        counter = 1
                        base_key = file_key
                        while file_key in content:
                            name_parts = base_key.rsplit('.', 1)
                            if len(name_parts) == 2:
                                base, ext = name_parts
                                file_key = f"{base} ({counter}).{ext}"
                            else:
                                file_key = f"{base_key} ({counter})"
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

        except Exception as e:
            logger.exception(f"文档上传处理失败: {str(e)}")
            # 返回原始状态，避免 UI 卡住
            return current_docs, current_content, f"❌ 上传失败: {str(e)}", gr.update(choices=list(current_content.keys()) if current_content else [])

    def _on_preview_doc(docs_content, selected_name):
        """预览文档内容（按文件名查找）"""
        if not docs_content or not selected_name:
            return ""

        return docs_content.get(selected_name, f"未找到文档: {selected_name}")

    def _on_save(project_id, name, desc, sources, tech, high, note, docs_content, author, platform, company_choice):
        """保存项目"""
        logger = logging.getLogger(__name__)
        if not project_id or not name:
            return "❌ 项目 ID 和名称不能为空", gr.update()  # 返回空更新，不刷新项目列表

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
            # 如果没有新文档内容，保留已存在的文档（不删除）
            # 只有当用户明确清空文档时才会删除（通过 clear_docs_btn）
            if project_docs_dir.exists():
                # 保留现有文档，只记录路径
                for doc_file in project_docs_dir.iterdir():
                    if doc_file.is_file():
                        docs_list.append(f"{project_id}/{doc_file.name}")
                logger.info(f"保留现有文档: {len(docs_list)} 个")

        # 确定最终使用的作者（优先使用项目配置，否则根据平台选择）
        final_author = author
        if not final_author:
            # 根据平台自动选择作者
            final_author = config.get_author_by_platform(platform)
            if final_author:
                logger.info(f"根据平台 {platform} 自动选择作者: {final_author}")

        # 解析公司选择
        company_id = None
        if company_choice and company_choice != "无公司（个人项目）":
            # 从 "公司名称 (id)" 格式中提取 ID
            if "(" in company_choice and company_choice.endswith(")"):
                company_id = company_choice[company_choice.rfind("(") + 1:-1]
                logger.info(f"项目关联公司: {company_id}")

        project_data = {
            "id": project_id,
            "name": name,
            "description": desc,
            "sources": sources or [],
            "tech_stack": tech_list,
            "highlights": high_list,
            "notes": note,
            "author": final_author or None,  # 优先使用项目配置，否则根据平台自动选择
            "git_platform": platform or "GitHub",  # Git 平台
            "company_id": company_id,  # 关联的公司ID（可为null表示个人项目）
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

        # 刷新项目列表
        projects = loader.get_projects()
        project_choices = [f"{p.get('id', '')} - {p.get('name', '')}" for p in projects]

        return msg, gr.update(choices=project_choices, value=None)

    def _on_delete(project_id):
        """删除项目"""
        if not project_id:
            # 返回空值（13 个输出）
            projects = loader.get_projects()
            project_choices = [f"{p.get('id', '')} - {p.get('name', '')}" for p in projects]
            return "❌ 请输入要删除的项目 ID", gr.update(choices=project_choices)

        # 删除文档目录
        project_docs_dir = DOCS_BASE_DIR / project_id
        if project_docs_dir.exists():
            import shutil
            shutil.rmtree(project_docs_dir)

        if loader.delete_project(project_id):
            # 刷新项目列表
            projects = loader.get_projects()
            project_choices = [f"{p.get('id', '')} - {p.get('name', '')}" for p in projects]
            return f"✅ 项目已删除: {project_id}", gr.update(choices=project_choices)
        else:
            projects = loader.get_projects()
            project_choices = [f"{p.get('id', '')} - {p.get('name', '')}" for p in projects]
            return f"❌ 项目不存在: {project_id}", gr.update(choices=project_choices)

    def _on_view_project(selected_project):
        """查看项目详情"""
        if not selected_project:
            return "*请选择一个项目*"

        # 从 "ID - 名称" 中提取 ID
        project_id = selected_project.split(" - ")[0].strip()

        data = loader.load_config()
        projects = data.get("projects", [])
        project = next((p for p in projects if p.get("id") == project_id), None)

        if not project:
            return f"*项目不存在: {project_id}*"

        # 格式化项目信息
        sources = project.get("sources", [])
        tech_stack = project.get("tech_stack", [])
        highlights = project.get("highlights", [])

        sources_text = "\n".join([f"- {s.get('path', '')} ({s.get('branch', '')})" for s in sources])

        detail = f"""## {project.get('name', '')} (`{project.get('id', '')}`)

**描述**: {project.get('description', '')}

**技术栈**: {', '.join(tech_stack) if tech_stack else '无'}

**项目亮点**:
{chr(10).join([f'- {h}' for h in highlights]) if highlights else '- 无'}

**仓库来源**:
{sources_text if sources_text else '- 无'}

**备注**: {project.get('notes', '无')}

**文档数量**: {len(project.get('docs', []))} 个
"""
        return detail

    def _refresh_project_list():
        """刷新项目列表选项"""
        projects = loader.get_projects()
        project_choices = [f"{p.get('id', '')} - {p.get('name', '')}" for p in projects]
        return gr.update(choices=project_choices, value=None)

    def _on_load_project(project_id):
        """加载项目到表单"""
        # 扫描仓库获取选项
        base_dir = loader.config.get_base_dir() if hasattr(loader, 'config') else "C:\\Users\\sherry\\project"
        project_dirs = loader.config.get_project_dirs() if hasattr(loader, 'config') else []
        repos = _scan_repos(base_dir, project_dirs)
        repo_choices = [r["name"] for r in repos]
        repo_choices.sort()

        # 获取公司列表
        from integrations.company.company_service import CompanyService
        company_service = CompanyService()
        company_choices = company_service.get_company_choices()

        if not project_id:
            # 返回空值（16 个输出，添加了 company_selector）
            return (
                "❌ 请输入要加载的项目 ID",  # status
                "",  # name
                "",  # description
                [],  # sources
                "",  # tech
                "",  # highlights
                "",  # notes
                "",  # author
                "GitHub",  # git_platform
                gr.update(choices=repo_choices, value=repo_choices[0] if repo_choices else None),  # repo_selector
                gr.update(value="main"),  # repo_branch
                [],  # docs_display
                {},  # docs_content_state
                gr.update(choices=[], value=None),  # doc_selector
                "",  # docs_preview
                "无公司（个人项目）""",  # company_selector
            )

        data = loader.load_config()
        projects = data.get("projects", [])

        # 查找项目
        project = next((p for p in projects if p.get("id") == project_id), None)

        if not project:
            # 返回空值（16 个输出，添加了 company_selector）
            return (
                f"❌ 项目不存在: {project_id}",  # status
                "",  # name
                "",  # description
                [],  # sources
                "",  # tech
                "",  # highlights
                "",  # notes
                "",  # author
                "GitHub",  # git_platform
                gr.update(choices=repo_choices, value=repo_choices[0] if repo_choices else None),  # repo_selector
                gr.update(value="main"),  # repo_branch
                [],  # docs_display
                {},  # docs_content_state
                gr.update(choices=[], value=None),  # doc_selector
                "",  # docs_preview
                "无公司（个人项目）""",  # company_selector
            )

        # 格式化数据用于表单
        sources = project.get("sources", [])
        tech_stack = project.get("tech_stack", [])
        highlights = project.get("highlights", [])

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

        # 获取公司选择值
        company_choice = "无公司（个人项目）"
        company_id = project.get("company_id")
        if company_id:
            company = company_service.get_company_by_id(company_id)
            if company:
                company_choice = f"{company['name']} ({company['id']})"

        # 返回表单数据
        return (
            f"✅ 已加载项目: {project.get('name', '')}",  # status
            project.get("name", ""),  # name
            project.get("description", ""),  # description
            sources,  # sources
            ", ".join(tech_stack) if tech_stack else "",  # tech
            "\n".join(highlights) if highlights else "",  # highlights
            project.get("notes", ""),  # notes
            project.get("author", ""),  # author
            project.get("git_platform", "GitHub"),  # git_platform
            gr.update(choices=repo_choices, value=repo_choices[0] if repo_choices else None),  # repo_selector update
            gr.update(value=default_branch),  # repo_branch update
            docs_list,  # docs_display
            docs_content,  # docs_content_state
            gr.update(choices=doc_choices, value=doc_choices[0] if doc_choices else None),  # doc_selector update
            docs_content.get(doc_choices[0], "") if doc_choices else "",  # docs_preview
            company_choice,  # company_selector
        )

    # 绑定事件
    repo_selector.change(
        fn=_on_repo_change,
        inputs=[repo_selector],
        outputs=[repo_branch]
    )

    add_source_btn.click(
        fn=_on_add_source,
        inputs=[sources_display, repo_selector, repo_branch, is_primary],
        outputs=[sources_display, status, is_primary]
    )

    clear_sources_btn.click(
        fn=_on_clear_sources,
        inputs=[],
        outputs=[sources_display, status, is_primary]
    )

    project_docs.upload(
        fn=_on_upload_docs,
        inputs=[project_docs, docs_display, docs_content_state, doc_project_selector, manual_project_selector],
        outputs=[docs_display, docs_content_state, status, doc_selector]
    )

    # 文档来源选择变化
    doc_project_selector.change(
        fn=_on_doc_project_change,
        inputs=[doc_project_selector, sources_display],
        outputs=[manual_project_group]
    )

    # Git 平台切换时自动填充作者
    def _on_platform_change(platform):
        """平台切换时，自动填充对应的作者"""
        if platform:
            author = config.get_author_by_platform(platform)
            if author:
                return gr.update(value=author, info=f"已自动填充 {platform} 作者")
        return gr.update(value=None)

    git_platform.change(
        fn=_on_platform_change,
        inputs=[git_platform],
        outputs=[project_author]
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
    def _on_analyze_docs(docs_content, sources):
        """分析文档，自动填充项目信息"""
        if not docs_content:
            return "❌ 请先上传文档", "", "", ""

        try:
            from src.core.agents.document_analyzer import DocumentAnalyzerAgent
            analyzer = DocumentAnalyzerAgent()

            # 如果有多个来源且标记了主项目，优先使用主项目文档
            primary_docs = {}
            if sources and len(sources) > 0:
                # 查找主项目
                primary_source = next((s for s in sources if s.get("primary")), None)
                if primary_source:
                    primary_path = primary_source.get("path", "")
                    # 提取主项目名称（用于文件名前缀匹配）
                    primary_name = primary_path.split("\\")[-1].split("/")[-1].lower()

                    import logging
                    logging.info(f"检测到主项目: {primary_name}")

                    # 筛选主项目相关的文档（优先检查文件名前缀）
                    for filename, content in docs_content.items():
                        filename_lower = filename.lower()

                        # 方法1: 检查文件名前缀（最准确）
                        if filename_lower.startswith(primary_name + "_"):
                            primary_docs[filename] = content
                            logging.info(f"✓ 文件名匹配: {filename}")
                            continue

                        # 方法2: 检查文件名是否包含项目名
                        if primary_name in filename_lower:
                            primary_docs[filename] = content
                            logging.info(f"✓ 文件名包含项目名: {filename}")
                            continue

                        # 方法3: 检查文档标题（从文档中提取项目名）
                        extracted_project = _extract_project_from_doc(content)
                        if extracted_project == primary_name.replace("-", "").replace("_", ""):
                            primary_docs[filename] = content
                            logging.info(f"✓ 文档标题匹配: {filename}")
                            continue

                    logging.info(f"主项目 {primary_name} 匹配到 {len(primary_docs)} 个文档")

            # 使用主项目文档（如果有），否则使用所有文档
            docs_to_analyze = primary_docs if primary_docs else docs_content

            if primary_docs:
                import logging
                logging.info(f"使用主项目文档分析: {list(primary_docs.keys())}")

            # 分析文档
            result = analyzer.analyze(docs_to_analyze)

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
        inputs=[docs_content_state, sources_display],
        outputs=[status, project_desc, tech_stack, highlights]
    )

    # 查看项目详情
    view_btn.click(
        fn=_on_view_project,
        inputs=[project_selector],
        outputs=[project_detail]
    )

    save_btn.click(
        fn=_on_save,
        inputs=[project_id, project_name, project_desc, sources_display, tech_stack, highlights, notes, docs_content_state, project_author, git_platform, company_selector],
        outputs=[status, project_selector]
    )

    delete_btn.click(
        fn=_on_delete,
        inputs=[project_id],
        outputs=[status, project_selector]
    )

    load_btn.click(
        fn=_on_load_project,
        inputs=[project_id],
        outputs=[status, project_name, project_desc, sources_display, tech_stack, highlights, notes, project_author, git_platform, repo_selector, repo_branch, docs_display, docs_content_state, doc_selector, docs_preview, company_selector]
    )
