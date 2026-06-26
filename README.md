# NAPS Git 周报 / 日报 / 简历生成器

基于 Git 提交记录自动生成**周报**、**日报**和**简历**，使用 **LangGraph Agent 工作流** + **Gradio Web 界面**，支持 Ollama / DeepSeek / OpenAI 等多种 LLM。当前版本 **V0.7.4**。

## ✨ 主要功能

三个功能在同一个 Gradio 界面以 Tab 形式提供：

| Tab | 功能 | 输出 |
|-----|------|------|
| 📊 周报 | 按 commits 生成周报（本周工作 + 下周计划，带状态枚举） | Markdown |
| 📅 日报 | 复用周报管线，**无状态枚举 / 不限条数 / 同模块合并**，每天给领导发 | Markdown |
| 📄 简历生成 | 从多个项目提取信息生成简历（项目经验 + bullets + 公司工作经历） | Word docx |

> **日报与周报的差异**：日报复用周报整条管线，只换提示词和规则——日报不写 `(对接中)(已提测)(已发布)` 状态、不限条数、同一模块的多个提交合并成一条；周报逻辑（状态枚举、下周计划）保持不变。

## 🤖 AI Agent 驱动

采用 **多 Agent 协作**，通过 LangGraph 实现工作流编排。

### 周报 / 日报工作流（带循环）

```
super_agent ──→ generator ──→ reviewer ──┐
     ▲                                   │
     └───────────────────────────────────┘
     └──→ END（规则判断通过）
```

周报和日报**共用同一条工作流**，通过 `mode` 切换提示词：周报（`simple`/`professional`）走 `weekly_report/` 提示词，日报（`daily`）走 `daily_report/` 提示词。`super_agent` 纯规则判断不用 LLM。

### 简历生成工作流（线性）

```
filter_resume → classify → aggregate → generate → END
```

所有 LLM 输出和 fallback 输出都过 `sanitize_resume_generation` 清洗（去夸大词、虚假百分比、技术手段当贡献、跨项目串内容）。

### 核心组件

| 组件 | 说明 |
|------|------|
| GeneratorAgent | 生成周报/日报/简历内容 |
| ReviewerAgent | 审查格式与质量，输出优化内容（日报用放松版 reviewer） |
| SuperAgent | 纯规则判断（OutputValidator + 最大迭代次数），决定继续还是结束 |
| DefaultCommitClassifier | Commit 模块分类（关键词匹配，零成本） |
| ModuleAggregator / CommitAggregator | 按模块聚合 commits |
| BulletGeneratorAgent / CompanySummarizerAgent | 简历 bullets / 公司工作经历 |

## 快速开始

### Docker 部署（推荐）

```bash
# Git Bash / Linux / macOS
bash start.sh

# Windows CMD
start.bat
```

访问 http://localhost:7861

`start.sh` 会自动完成：
- **同步配置**：把仓库 `config/*.json` 复制到 `~/.naps/`（仓库 `config/` 是唯一来源，改配置只需编辑仓库 `config/` 后重跑 `start.sh`，不用重新 build）
- **构建镜像**：默认走清华 PyPI 镜像（国内网络 pypi.org 不稳），可用 `PIP_INDEX_URL` 环境变量覆盖
- **挂载**：宿主项目目录只读挂载、输出目录可写

### 本地开发

```bash
pip install -r requirements.txt
python -m src.ui.gradio_server          # Gradio :7860
```

## 配置

> 主程序读 `config/naps.json`（路径来自环境变量 `NAPS_CONFIG_PATH`），项目定义在 `config/projects.json`。
> **根目录 `config.json` 是遗留文件，主程序不读**，改配置请编辑 `config/naps.json`。

### config/naps.json

```json
{
  "author": "caihong <caihong@zxfintec.com>",
  "base_dir": "C:\\Users\\sherry",
  "project_dirs": ["C:\\Users\\sherry\\project"],
  "llm": {
    "provider": "ollama",
    "model": "llama3.1:8b",
    "api_base": "http://localhost:11434",
    "api_key": "",
    "timeout": 120,
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "langsmith": { "enabled": false, "project": "naps_generator" },
  "output_dir": "./output"
}
```

- **author**：周报/日报按此作者过滤 commits（`name <email>` 必须和 git 提交人一致，否则过滤不到）
- **langsmith.api_key**：留空则走环境变量 `LANGCHAIN_API_KEY`（不要把密钥写进版本库）

### config/projects.json

简历项目定义：每个项目含 `id`、`name`、`sources`（仓库路径 + 分支）、`modules`（模块名 + 关键词）、`author`、`company_id` 等。

### LLM 提供商

| 提供商 | provider | 说明 |
|--------|----------|------|
| Ollama | `ollama` | 本地运行，Docker 内自动把 localhost 替换为 host.docker.internal |
| DeepSeek | `deepseek` | 需要 `api_key` |
| OpenAI | `openai` | 需要 `api_key` |

### LangSmith 可观测性

`config/naps.json` 设 `"langsmith": {"enabled": true}`，api_key 优先 config、没有则用环境变量：

```bash
export LANGCHAIN_API_KEY="lsv2_pt_..."
bash start.sh
```

## 项目结构

```
src/
├── ui/
│   ├── gradio_server.py        # Gradio 入口；create_ui() 用 gr.Tabs 挂 周报/日报/简历
│   └── tabs/                   # 各功能 Tab（create_*_tab）
│       ├── weekly_report_tab.py
│       ├── daily_report_tab.py
│       ├── resume_generate_tab.py
│       ├── resume_manage_tab.py
│       └── company_manage_tab.py
├── core/
│   ├── workflow/               # graph.py(周报/日报) · resume_graph.py(简历) · state.py
│   ├── agents/                 # generator · reviewer · super_agent · *_summarizer · bullet_generator
│   ├── git/                    # commit_fetcher · task_classifier · commit_splitter ·
│   │                           #   commit_aggregator · module_aggregator · default_classifier · repo
│   ├── llm/client.py           # LLM 客户端工厂（Ollama/DeepSeek/OpenAI）
│   └── validators/             # output.py(OutputValidator) · resume_content.py(简历清洗)
├── integrations/
│   ├── git_report/report_service.py     # 周报服务（含 _group_by_scope 同模块合并）
│   ├── daily_report/daily_report_service.py  # 日报服务（继承 ReportService）
│   ├── resume/                          # resume_service · config_loader · document_builder · resume_parser
│   └── company/company_service.py
├── prompts/                    # weekly_report/ · daily_report/ · resume/ · commit/ · company/
└── config.py                   # Config：读 naps.json，提供 get_author/to_container_path 等
```

## 使用流程

### 周报 / 日报
1. 选项目 → 选分支（可多选）→ 添加到列表
2. 设天数范围（周报默认 7 天；**日报默认 1 天，按东八区严格计算**）
3. 周报选模式（简约/专业）→ 点生成；日报直接点生成
4. 查看结果、下载

### 简历生成
1. 勾选要包含的项目
2. （可选）上传历史简历，在其基础上追加新项目
3. 点生成 → 下载 Word 文档

## 测试

```bash
# 本机若有 Python
python -m pytest tests/ -v

# 本机通常无可用 Python：进容器跑（Git Bash 加 MSYS_NO_PATHCONV=1）
docker exec -w /app -e PYTHONPATH=/app:/app/src naps-generator python -m pytest tests/ -v
```

## Docker 常用命令

```bash
docker logs -f naps-generator      # 查看日志
docker stop naps-generator         # 停止
docker restart naps-generator      # 重启
docker rm -f naps-generator        # 删除容器
```

> **挂载说明**：宿主 `C:\Users\sherry\project` 只读挂载到 `/app/project`，工具读的是这份。若你在别处开发，记得在 `C:\Users\sherry\project\<repo>` 里 `git pull`，否则容器看不到最新提交。

## 版本历史

| 版本 | 内容 |
|------|------|
| **V0.7.4** | **日报生成模块（无状态枚举/不限条数/合并同模块）；时区修复（东八区）；merge commit 过滤** |
| V0.7.3 | 简历清洗 guardrails；Docker 部署修复（镜像源/挂载/config 自动同步）；简历 UI；LangSmith env 化；CLAUDE.md |
| V0.7.2 | 公司工作经历生成 + 简历/周报优化 |
| V0.7 | 简历生成系统（基于 Git commits 自动生成） |
| V0.6 | LangGraph Agent 工作流 + LangSmith 集成 |
| V0.5 | 摘要生成优化 |
| V0.4 | Task 聚合（高层任务抽象） |
| V0.3 | Commit 拆分（结构化子任务） |
| V0.2 | Commit 过滤与分类 |
| V0.1 | 基础周报生成 |

## 许可证

MIT License
