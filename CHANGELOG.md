# CHANGELOG

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

