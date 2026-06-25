# CHANGELOG

## [v0.7.3] - 2026-06-25

### ✨ 新功能

- feat: 简历生成内容清洗 guardrails（`resume_content.py`，跨项目内容/夸大词/虚假百分比/技术手段当贡献）
- feat: 简历生成 Tab 接入 Gradio UI（`gradio_server` 改用 `gr.Tabs`）
- feat: 简历 Docker 路径转换（`Config.to_container_path`，宿主路径 → `/app/project`）
- feat: Docker 部署时自动同步 `config/` 到 `~/.naps/`（仓库 config 为唯一来源，消除漂移）
- feat: LangSmith `api_key` 支持环境变量 `LANGCHAIN_API_KEY`（不把密钥写进版本库）

### 🐛 问题修复

- fix: Docker 容器崩溃循环（`langchain_ollama` 缺失，重建镜像烤入依赖）
- fix: 周报「当前项目」下拉和分支为空（挂载路径 `projects` → `project`）
- fix: 周报生成 `IsADirectoryError: /app`（author 占位符过滤不到 commits、空文件返回 `None`、`_save_report` 返回绝对路径）
- fix: naps 模块分类（收单 → 收单支付、投诉 → 投诉），最低模块提交数 2 → 1

### 📝 文档 / 构建

- 新增 `CLAUDE.md`（架构地图、关键文件、运行/测试/部署、配置架构、坑）
- `Dockerfile` 加 `PIP_INDEX_URL` 镜像源参数；`start.sh` 修正挂载与构建镜像源

## [v0.7.2] - 2026-04-30

### ✨ 新功能

- feat: 公司工作经历生成（CompanySummarizerAgent）
- feat: 项目名称前缀隔离（防止不同项目的模块混淆）
- feat: 公司管理 Tab（公司信息增删改查）

### 🐛 问题修复

- fix: 简历模块混淆问题（添加项目名称前缀【项目名】）
- fix: 周报状态判定错误（近7天默认已提测/对接中）
- fix: 周报内容过长（添加20字简洁性要求）
- fix: 周报夸大词问题（禁止"多种"、"多个"、"全面"）

### 📝 提示词优化

- prompts/company/work_experience_generator.txt（50字简洁性）
- prompts/resume/resume_module_generator.txt（项目前缀要求）
- prompts/weekly_report/generator_simple.txt（状态判定+简洁性）
- prompts/weekly_report/reviewer_strict.txt（新增简洁性检查规则）

### ♻️ 代码重构

- refactor: fallback 策略添加项目标识
- refactor: 模块分类器（DefaultCommitClassifier）
- refactor: 模块聚合器（ModuleAggregator）

---

## [v0.7] - 2026-04-10

### ✨ 新功能

- feat: 简历生成系统（基于 Git commits 自动生成简历 bullets）
- feat: 公共 Git 模块（core.git）- 周报和简历共享
- feat: 项目总结 Agent（压缩大量 commit 信息）
- feat: Bullet 生成 Agent（基于摘要 + claude.md + readme 生成 bullets）
- feat: 项目管理 Tab（仓库选择、分支选择、文档上传）
- feat: 文档智能分析（自动提取项目描述、技术栈、亮点）
- feat: 历史简历上传（基于现有简历修改）
- feat: Word 文档导出（python-docx）
- feat: 提示词目录重构（common / weekly_report / resume）

### 🐛 问题修复

- fix: 文档存储优化（从 JSON 内联改为文件系统存储，按项目分目录）
- fix: 项目描述优化（业务场景 + 技术能力格式，80-120 字）
- fix: UI 布局改进（加载/删除按钮移到顶部）
- fix: 文档上传去重（内容相同则覆盖，不同则添加序号）
- fix: CommitFetcher 统一接口（days 参数控制周报/简历）
- fix: 配置文件路径支持环境变量（NAPS_CONFIG_PATH, NAPS_PROJECTS_PATH）
- fix: UI 模块拆分（main.py + tabs/）
- fix: DOCS_BASE_DIR 路径层级错误（3 层改为 4 层）
- fix: 保存时清理旧文档（删除残留文件）

### 📝 文档

- docs: 添加 V0.7 设计文档
- docs: 添加配置示例文件（config/*.example）
- docs: 更新 .gitignore（配置文件不提交）

### ♻️ 代码重构

- refactor: 抽取公共 Git 模块（core.git）
- refactor: 重构提示词目录结构（按功能分类）
- refactor: 文档分析 Agent 优化（JSON/Text 双解析模式）

### ✅ 测试

- test: 新增 14 个 V0.7 测试用例
- test: 全部 116 个测试通过

### 🔧 其他

- config: 支持环境变量覆盖配置路径
- config: 默认配置文件（config/naps.json, config/projects.json）
- config: 文档存储结构（config/docs/{project_id}/）
- docker: 更新部署脚本（挂载用户配置目录）

---

## [v0.6] - 2026-04-09

### ✨ 新功能

- feat: LangGraph StateGraph Agent 工作流（super_agent → generator → reviewer 循环）
- feat: LLM 客户端工厂，支持 Ollama / DeepSeek / OpenAI
- feat: Docker 内自动检测 host.docker.internal 连接 Ollama
- feat: LangSmith 可观测性集成（环境变量配置）
- feat: OutputValidator 输出校验（长度/结构/模式）
- feat: Gradio Web UI（项目选择、分支、简约/专业模式切换）
- feat: reviewer 审查结果未通过时自动触发重新生成

### 🐛 问题修复

- fix: reviewer passed=false 时 super_agent 不再忽略，触发重新生成
- fix: summary 输出清理引号、书名号等包裹符号
- fix: summary prompt 禁止日语输出，控制字数在 20 字以内
- fix: Docker 端口映射（7861:7860）
- fix: Git Bash MSYS 路径转换问题

### 📝 文档

- docs: 重写 README.md，包含架构图、项目结构、LangSmith 配置

### ♻️ 代码重构

- refactor: 重构为 core（框架）/ integrations（业务）/ ui（界面）三层架构
- refactor: 移除 super_agent LLM 检查（规则判断即可，避免错误反馈）
- refactor: Prompt 文件独立管理，缺失时抛 FileNotFoundError

### ✅ 测试

- test: 102 个测试用例全部通过

## [v0.5] - 2026-04-07

### ✨ 新功能

- feat: V0.5 摘要生成优化
- feat: V0.4 添加聚合功能
- feat: V0.3 添加 Commit 拆分功能
- feat: 增强日志输出，显示每条commit的处理详情
- feat: 添加 V0.2 处理过程日志输出
- feat: 实现V0.2版本 - Commit过滤与分类

### 🐛 问题修复

- fix: 修复多行commit message的解析问题
- fix: 修复 Docker 部署脚本问题
- fix: 修复原有测试的跨平台兼容性问题
- fix: Docker部署支持及提示词优化
- fix: Add README.md and update .gitignore

### 📝 文档

- docs: 添加 CHANGELOG for v0.4
- docs: 添加 CHANGELOG for v0.4
- docs: 添加 CHANGELOG for v0.3
- docs: 添加 CHANGELOG for V0.2
- docs: 更新 README 添加 V0.2 功能说明

### ♻️ 代码重构

- refactor: 拆分 prompt 为独立文件

### ✅ 测试

- test: 添加 ReportApp 边界测试用例 (V0.2)

### 🔧 其他

- debug: 添加更详细的调试日志
- config: 添加Docker环境api_base配置说明
- Initial commit: Git Weekly Report Generator v0.1

