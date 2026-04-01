# NAPS Git周报生成器

基于Git提交记录自动生成周报的工具，使用Gradio提供Web界面，支持多种LLM提供商（Ollama、DeepSeek、OpenAI）。

## 功能特性

### V0.2 新增
- 🔍 **智能过滤**：自动过滤 Merge branch、test commit、短消息
- 🏷️ **自动分类**：支持标准格式（Conventional Commits）和关键词分类
- 📝 **详细日志**：显示每条 commit 的处理过程（过滤原因、分类结果）
- 📊 **结构化输出**：输出 JSON 格式的分类结果
- ✅ **完整测试**：48个测试用例覆盖核心功能

### 基础功能
- 📊 自动从Git仓库提取指定时间范围的提交记录
- 🤖 使用LLM生成简洁易懂的周报
- 🎯 支持按作者筛选提交记录
- 🌐 友好的Web界面（Gradio）
- 📥 支持下载生成的周报（Markdown格式）
- 🐳 支持Docker部署
- ⚙️ 灵活的配置管理

## 版本历史

### V0.2 (当前)
- Commit 过滤：丢弃 Merge branch、test、短消息
- Commit 分类：支持标准格式和关键词分类
- 支持多行 commit message 解析
- 详细日志输出

### V0.1
- 基础周报生成功能
- 多项目、多分支支持
- Gradio Web 界面

## 快速开始

### 1. 配置

编辑 `config.json` 文件，配置作者信息和LLM设置：

```json
{
  "author": "Your Name <your.email@example.com>",
  "llm": {
    "provider": "ollama",
    "model": "qwen2.5:14b",
    "api_base": "http://host.docker.internal:11434",
    "api_key": "",
    "timeout": 120,
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "output_dir": "/app/output"
}
```

### 2. 使用Docker部署

```bash
# 启动服务（自动构建并运行）
./start.sh

# 停止服务
./stop.sh
```

服务启动后访问: http://localhost:7861

### 3. 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python -m src.app
```

## 配置说明

### LLM提供商

支持三种LLM提供商：

#### Ollama（推荐）
```json
{
  "provider": "ollama",
  "model": "qwen2.5:14b",
  "api_base": "http://host.docker.internal:11434"
}
```

#### DeepSeek
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat",
  "api_key": "your-api-key",
  "api_base": "https://api.deepseek.com"
}
```

#### OpenAI
```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "api_key": "your-api-key",
  "api_base": "https://api.openai.com/v1"
}
```

### 作者配置

在 `config.json` 中配置你的Git用户信息，用于筛选提交记录：

```json
{
  "author": "Your Name <your.email@example.com>"
}
```

可以通过以下命令查看你的Git配置：

```bash
git config user.name
git config user.email
```

## Commit 分类规则（V0.2）

### 标准格式

支持 Conventional Commits 格式：`type(scope): message`

| Type | 分类 | 说明 |
|------|------|------|
| feat | feature | 新功能 |
| fix | fix | 问题修复 |
| refactor | refactor | 代码重构 |

示例：
```
feat(perms): 添加角色权限管理
fix(auth): 修复登录问题
refactor(db): 优化数据库查询
```

### 关键词分类

对于非标准格式的 commit，根据关键词自动分类：

| 关键词 | 分类 |
|--------|------|
| 发布、上线、新加坡、德国、巴西 | feature |
| 修复、bug、问题 | fix |
| 其他 | refactor |

### 过滤规则

以下 commit 会被自动过滤：
- 包含 `Merge branch` 的合并提交
- 包含 `test` 的测试提交
- 消息长度 < 5 的提交

## 目录结构

```
naps_report_generator/
├── src/
│   ├── prompt/
│   │   ├── system_prompt.txt    # 系统提示词
│   │   └── user_prompt.txt      # 用户提示词
│   ├── commit_processor.py      # V0.2: Commit过滤和分类
│   ├── config.py                # 配置管理
│   ├── git_utils.py             # Git工具
│   ├── llm_client.py            # LLM客户端
│   ├── app.py                   # Gradio应用入口
│   └── report_generator.py      # 报告生成器
├── tests/                       # 测试用例
│   ├── test_commit_processor.py # V0.2: 分类测试
│   ├── test_app.py              # V0.2: 边界测试
│   ├── test_git_utils.py
│   ├── test_llm_client.py
│   └── test_config.py
├── config.json                  # 配置文件
├── requirements.txt             # Python依赖
├── Dockerfile                   # Docker镜像
├── start.sh                     # 启动脚本
├── stop.sh                      # 停止脚本
└── README.md                    # 项目说明
```

## 使用说明

1. 在Web界面选择项目和分支
2. 设置时间范围（天数）
3. 点击"生成周报"按钮
4. 查看生成的周报内容并下载

## 查看处理日志

V0.2 会显示详细的处理日志：

```bash
docker logs --tail 100 report-generator
```

日志示例：
```
============================================================
V0.2: Commit 处理开始
收集到 50 条原始 commit
============================================================
>>> 步骤1: 过滤 commit
  [过滤] abc123 | Merge branch | Merge branch 'feature'
过滤统计: {'Merge branch': 5, '包含test': 3}
============================================================
>>> 步骤2: 分类 commit
  [feature/perms] def456 | feat(perms): 添加权限管理
  [fix/auth] ghi789 | fix(auth): 修复登录问题
>>> 分类统计: {'feature': 20, 'fix': 10, 'refactor': 5}
============================================================
```

## 测试

```bash
# 运行所有测试
python -m unittest discover tests

# 运行单个测试文件
python -m unittest tests.test_commit_processor
python -m unittest tests.test_git_utils
python -m unittest tests.test_llm_client
python -m unittest tests.test_config
python -m unittest tests.test_app
```

## Docker命令说明

启动容器使用的命令：
```bash
docker run -d \
    --name report-generator \
    -p 7861:7860 \
    -v "C:/Users/sherry/project/naps_report_generator/config.json:/app/config.json" \
    -v "C:/Users/sherry/project/naps_report_generator/output:/app/output" \
    -v "C:/Users/sherry/project:/app/project:ro" \
    -e PROJECT_BASE_DIR=/app/project \
    --add-host=host.docker.internal:host-gateway \
    --restart unless-stopped \
    naps-report-generator:main-v0.2
```

常用命令：
```bash
# 查看日志
docker logs -f report-generator

# 查看最近日志
docker logs --tail 50 report-generator

# 进入容器
docker exec -it report-generator bash

# 重启容器
docker restart report-generator
```

## 开发路线图

- [x] V0.1: 基础周报生成
- [x] V0.2: Commit 过滤与分类
- [ ] V0.3: Commit 拆分（结构化子任务）
- [ ] V0.4: Task 聚合（高层任务抽象）

## 注意事项

- 确保Docker容器可以访问Git仓库
- 使用Ollama时，确保Ollama服务正在运行
- 生成的周报保存在 `output/` 目录中
- 周报仅包含配置中指定的作者的提交记录

## 许可证

MIT License
