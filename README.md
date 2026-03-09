# NAPS Git周报生成器

基于Git提交记录自动生成周报的工具，使用Gradio提供Web界面，支持多种LLM提供商（Ollama、DeepSeek、OpenAI）。

## 功能特性

- 📊 自动从Git仓库提取指定时间范围的提交记录
- 🤖 使用LLM生成简洁易懂的周报
- 🎯 支持按作者筛选提交记录
- 🌐 友好的Web界面（Gradio）
- 📥 支持下载生成的周报（Markdown格式）
- 🐳 支持Docker部署
- ⚙️ 灵活的配置管理

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
# 启动服务
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
python -m src.gradio
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

## 目录结构

```
naps_report_generator/
├── src/
│   ├── prompt/
│   │   ├── system_prompt.txt    # 系统提示词
│   │   └── user_prompt.txt      # 用户提示词
│   ├── config.py                # 配置管理
│   ├── git_utils.py             # Git工具
│   ├── llm_client.py            # LLM客户端
│   ├── report_generator.py      # 报告生成器
│   └── gradio.py                # Gradio应用
├── tests/                       # 测试用例
├── config.json                  # 配置文件
├── requirements.txt             # Python依赖
├── Dockerfile                   # Docker镜像
├── start.sh                     # 启动脚本
├── stop.sh                      # 停止脚本
└── README.md                    # 项目说明
```

## 使用说明

1. 在Web界面输入Git仓库路径
2. 选择要生成周报的分支
3. 设置时间范围（天数）
4. 点击"生成周报"按钮
5. 查看生成的周报内容并下载

## 测试

```bash
# 运行所有测试
python tests/run_tests.py

# 运行单个测试文件
python -m unittest tests.test_git_utils
python -m unittest tests.test_llm_client
python -m unittest tests.test_config
```

## Docker命令说明

启动容器使用的命令：
```bash
docker run -d \
    --name naps-report-generator \
    -p 7861:7860 \
    -v "$(pwd)/config.json:/app/config.json" \
    -v "$(pwd)/output:/app/output" \
    --add-host=host.docker.internal:host-gateway \
    --restart unless-stopped \
    naps-report-generator
```

常用命令：
```bash
# 查看日志
docker logs -f naps-report-generator

# 进入容器
docker exec -it naps-report-generator bash

# 重启容器
docker restart naps-report-generator
```

## 注意事项

- 确保Docker容器可以访问Git仓库
- 使用Ollama时，确保Ollama服务正在运行
- 生成的周报保存在 `output/` 目录中
- 周报仅包含配置中指定的作者的提交记录

## 许可证

MIT License
