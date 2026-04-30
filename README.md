# NAPS Git 周报与简历生成器

基于 Git 提交记录自动生成周报和简历，使用 **LangGraph Agent 工作流** + **Gradio Web 界面**，支持 Ollama / DeepSeek / OpenAI 等多种 LLM。

## ✨ 主要功能

- **周报生成**: 根据 Git commits 自动生成格式规范的周报
- **简历生成**: 从多个项目中提取信息生成简历 bullets
- **公司工作经历**: 基于多个项目自动生成公司工作经历描述

## 🤖 AI Agent 驱动

本项目采用 **多 Agent 协作模式**，通过 LangGraph 实现工作流编排：

### 周报生成工作流
```
super_agent ──→ generator ──→ reviewer ──┐
     ▲                                   │
     └───────────────────────────────────┘
     │
     └──→ END (规则判断通过)
```

### 简历生成工作流
```
filter → classify → aggregate → generate → END
```

### 核心组件

| 组件 | 说明 | AI 能力 |
|------|------|---------|
| GeneratorAgent | 生成周报/简历内容 | LLM 文本生成 |
| ReviewerAgent | 审查内容质量 | LLM 格式校验 |
| CompanySummarizerAgent | 生成公司工作经历 | LLM 信息整合 |
| DefaultCommitClassifier | Commit 模块分类 | 关键词匹配（零成本） |
| BulletGeneratorAgent | 生成简历 bullets | LLM 受控表达 |

### AI 能力说明

1. **文本生成与优化**: LLM 根据 commits 生成符合格式要求的周报和简历内容
2. **格式校验与修正**: Reviewer Agent 自动检测并修正格式问题
3. **信息提取与整合**: 从多个项目中提取关键信息，生成公司工作经历
4. **模块化分类**: 基于关键词的 commit 分类，无需 LLM 调用
5. **循环优化**: Generator → Reviewer 循环迭代，持续改进内容质量

## 架构

```
用户输入 (Git commits)
        │
        ▼
┌─ LangGraph StateGraph ─────────────────────┐
│                                             │
│  super_agent ──→ generator ──→ reviewer ─┐  │
│       ▲                                  │  │
│       └──────────────────────────────────┘  │
│       │                                     │
│       └──→ END (规则判断通过)               │
└─────────────────────────────────────────────┘
        │
        ▼
    最终周报文本
```

- **super_agent**: 纯规则判断（OutputValidator + 最大迭代次数），决定继续生成还是结束
- **generator**: 根据 commit 数据和 reviewer 反馈生成/修改周报
- **reviewer**: 审查草稿质量，输出优化后的内容和问题列表
- **LangSmith**: 可选的可观测性追踪（Docker 环境通过环境变量配置）

## 快速开始

### Docker 部署（推荐）

```bash
# Linux / macOS / Git Bash
bash start.sh

# Windows CMD
start.bat
```

访问 http://localhost:7861

### 本地开发

```bash
pip install -r requirements.txt
python -m src.ui.gradio_server
```

## 配置

### config.json

```json
{
  "author": "Your Name <your.email@example.com>",
  "llm": {
    "provider": "ollama",
    "model": "llama3.1:8b",
    "api_base": "http://localhost:11434",
    "api_key": "",
    "timeout": 120,
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "langsmith": {
    "enabled": true,
    "project": "report_generator"
  },
  "output_dir": "./output"
}
```

### LLM 提供商

| 提供商 | provider | 说明 |
|--------|----------|------|
| Ollama | `ollama` | 本地运行，Docker 内自动将 localhost 替换为 host.docker.internal |
| DeepSeek | `deepseek` | 需要 `api_key` |
| OpenAI | `openai` | 需要 `api_key` |

### LangSmith 可观测性

**本地运行**: `config.json` 中设置 `"langsmith": {"enabled": true}` 并设置环境变量：

```bash
export LANGCHAIN_API_KEY="lsv2_pt_..."
```

**Docker 运行**: 环境变量通过 `start.sh` / `start.bat` 自动传入容器：

```bash
# 确保 shell 中已设置
export LANGCHAIN_API_KEY="lsv2_pt_..."

# 然后部署
bash start.sh
```

访问 [LangSmith](https://smith.langchain.com) 查看追踪记录。

## 项目结构

```
src/
├── core/                          # 核心框架
│   ├── agents/                    # Agent 实现
│   │   ├── base.py               # Agent 基类
│   │   ├── generator.py          # 生成器 Agent
│   │   ├── reviewer.py           # 审查器 Agent
│   │   └── super_agent.py        # 超级 Agent（规则判断）
│   ├── llm/                      # LLM 客户端
│   │   ├── base.py               # 客户端基类
│   │   └── client.py             # 工厂方法 + Ollama/DeepSeek/OpenAI 实现
│   ├── workflow/                  # LangGraph 工作流
│   │   ├── state.py              # WorkflowState 数据类
│   │   └── graph.py              # StateGraph 定义 + 节点函数
│   ├── validators/                # 输出校验
│   │   └── output.py             # OutputValidator
│   └── sources/                   # 数据源抽象
│       └── base.py               # 数据源基类
├── integrations/                  # 业务集成
│   └── git_report/               # Git 周报集成
│       ├── git_utils.py          # Git 操作工具
│       ├── report_service.py     # 周报服务（UI 调用入口）
│       ├── source.py             # Git 数据源
│       ├── commit_processor/     # Commit 处理管线
│       │   ├── filter_classifier.py  # 过滤 + 分类
│       │   ├── splitter.py           # Commit 拆分
│       │   ├── aggregator.py         # Task 聚合 + LLM 摘要
│       │   └── processor.py          # 处理管线编排
│       └── prompt/               # Commit 处理用提示词
├── prompts/                       # Agent 提示词
│   └── agents/                   # 各 Agent 的 prompt 文件
├── ui/                            # UI 层
│   └── gradio_server.py          # Gradio Web 界面
└── config.py                      # 配置管理
```

## 使用流程

1. 选择项目 → 选择分支 → 添加到列表
2. 设置天数范围（默认 7 天）
3. 选择模式：简约模式 / 专业模式
4. 点击"生成周报"
5. 查看结果并下载

## 测试

```bash
python -m pytest tests/ -v
```

当前 102 个测试用例覆盖：Commit 过滤/分类/拆分/聚合、Git 工具、LLM 客户端、配置管理、工作流状态、输出校验。

## Docker 常用命令

```bash
docker logs -f report-generator     # 查看日志
docker stop report-generator        # 停止
docker restart report-generator     # 重启
docker rm -f report-generator       # 删除
```

## 版本历史

| 版本 | 内容 |
|------|------|
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
