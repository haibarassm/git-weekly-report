# CLAUDE.md

本文件给在仓库里工作的开发者 / AI agent 看。用户向说明见 `README.md`。

## 项目简介

基于 Git 提交记录自动生成**周报**和**简历**的工具。Python 3.11 + LangGraph Agent 工作流 + Gradio Web 界面，支持 Ollama / DeepSeek / OpenAI。当前版本 V0.7.2。

## 两条核心流程

| 流程 | 服务入口 | 工作流 | 输出 |
|------|---------|--------|------|
| 周报 | `src/integrations/git_report/report_service.py` (`ReportService`) | `src/core/workflow/graph.py` `ContentGenerationWorkflow` | Markdown |
| 简历 | `src/integrations/resume/resume_service.py` (`ResumeService`) | `src/core/workflow/resume_graph.py` `ResumeGenerationWorkflow` | Word docx |

**周报工作流**（带循环）：`super_agent → generator → reviewer → super_agent`，规则判断通过后 END。`super_agent` 纯规则不用 LLM；最终内容从 reviewer 的 `optimized_content` 提取。

**简历工作流**（线性）：`filter_resume → classify → aggregate → generate`。LLM 输出和 fallback 输出都会过 `sanitize_resume_generation` 清洗（去夸大词、虚假百分比、技术手段当贡献、跨项目串内容）。

## 关键文件地图

```
src/
├── ui/
│   ├── gradio_server.py        # Gradio 入口 launch()；create_ui() 用 gr.Tabs 挂「周报」+「简历生成」
│   └── tabs/                   # 各功能 tab（create_*_tab 函数）
│       ├── weekly_report_tab.py
│       ├── resume_generate_tab.py   # create_resume_generate_tab(config)
│       ├── resume_manage_tab.py
│       └── company_manage_tab.py
├── core/
│   ├── workflow/
│   │   ├── graph.py            # 周报 StateGraph + 节点
│   │   ├── resume_graph.py     # 简历 StateGraph + 节点
│   │   └── state.py            # WorkflowState（通过 messages 传数据）
│   ├── agents/                 # generator / reviewer / super_agent / *_summarizer / bullet_generator
│   ├── git/                    # commit_fetcher / task_classifier / commit_splitter / commit_aggregator
│   │                           #   / module_aggregator / default_classifier / repo
│   ├── llm/client.py           # LLM 客户端工厂；Docker 内 localhost→host.docker.internal
│   └── validators/
│       ├── output.py           # OutputValidator
│       └── resume_content.py   # sanitize_resume_generation（简历清洗 guardrails）
├── integrations/
│   ├── git_report/report_service.py   # 周报服务
│   ├── resume/                       # 简历服务：resume_service / config_loader / document_builder / resume_parser
│   └── company/company_service.py
├── prompts/                    # Agent 提示词文件（.txt）
└── config.py                   # Config 类：读 naps.json，提供 get_author/get_llm_config/to_container_path 等
```

## 运行 / 测试 / 部署

```bash
# 本地调试
python -m src.ui.gradio_server          # Gradio :7860

# Docker 部署（推荐）
bash start.sh                            # 同步 config → 构建 → 启动，访问 :7861

# 测试（本机若无 Python，进容器跑）
.venv/Scripts/python.exe -m pytest tests/ -v
docker exec -w /app -e PYTHONPATH=/app:/app/src naps-generator python -m pytest tests/ -v
```

> **本机通常没有可用的 Python**（.venv 指向不存在）。验证代码改动最可靠的方式：进容器 `docker exec`（Git Bash 下加 `MSYS_NO_PATHCONV=1`）。

## 配置架构（单一来源）

- **`config/naps.json`**：主配置（author、llm、langsmith、output_dir、project_dirs）。由 `src/config.py` 的 `Config` 读取，路径来自环境变量 `NAPS_CONFIG_PATH`。
- **`config/projects.json`**：项目定义（id、name、sources[路径+分支]、modules、author、company_id）。由 `integrations/resume/config_loader.py` 读取。
- **根目录 `config.json` 是遗留文件，主程序不读**，别在这里改配置。
- **Docker 部署时 `start.sh` 会把仓库 `config/*.json` 同步到 `~/.naps/`** 再挂载进容器。所以**仓库 `config/` 是唯一来源**，改完配置重跑 `bash start.sh` 即可，不用重新 build 镜像。

## Docker 部署要点（坑）

- **PyPI 镜像源**：本机网络访问 pypi.org 会被掐 SSL。`Dockerfile` 用 `ARG PIP_INDEX_URL=`（默认 pypi 保持可移植），`start.sh` build 时默认传清华源 `https://pypi.tuna.tsinghua.edu.cn/simple`（可用 `PIP_INDEX_URL` 环境变量覆盖）。pip 层缓存后重建很快。
- **挂载路径**：宿主 `C:\Users\sherry\project` → 容器 `/app/project:ro`（**单数**，对齐 `PROJECT_BASE_DIR=/app/project`）。周报靠 `os.walk(base_dir)` 扫描挂载目录填充「当前项目」下拉和分支。
- **简历路径转换**：`projects.json` 里 source 路径是宿主绝对路径，`Config.to_container_path()` 在容器内把它们转成 `/app/project/...`（本地原样返回）。改取仓库路径的点在 `resume_service` 取 `source.get("path")` 处。
- **端口**：7861（host）→ 7860（container）。
- **LangSmith**：`_setup_langsmith` 在 `langsmith.enabled=true` 时启用，api_key 优先 config、没有则用环境变量 `LANGCHAIN_API_KEY`（**不要把密钥写进版本化的 config**）。默认 `enabled=false`。

## 设计决策与约定

- **super_agent 不用 LLM**：规则判断即可，LLM 会给错误反馈把正确内容改坏。
- **reviewer 有乱码检测**：`_is_content_coherent()` 用字符重叠度判断。
- **简历清洗**：所有简历生成输出（LLM + fallback）必过 `sanitize_resume_generation`。
- **Gradio 文件下载**：无文件时返回 `None` 不能返回 `""`（Gradio 6.9 会把 `""` 当路径解析成 cwd `/app` → `IsADirectoryError`）；文件路径用绝对路径（`Path.resolve()`）。
- **Prompt 文件缺失必须抛 FileNotFoundError**，不能静默返回空。
- **LangGraph 返回的是字典**，不是 WorkflowState 对象。
- **`MSYS_NO_PATHCONV=1`** 在 Git Bash 中处理 Docker / 容器内路径参数。
- 提交信息用中文，`feat:/fix:/docs:/refactor:` 等前缀。

## 数据来源

- **Git 仓库**：通过 `git` 在挂载的 `/app/project` 下读取（`CommitFetcher` 用 GitPython）。
- **LLM**：默认 Ollama（`llama3.1:8b`），通过 `host.docker.internal:11434` 访问宿主 ollama。
- **author 过滤**：周报按 `config/naps.json` 的 `author` 字段过滤 commits（当前 `caihong <caihong@zxfintec.com>`）。author 不对会过滤不到任何提交。
