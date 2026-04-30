# 简历生成系统 - LLM 生成内容问题分析

## 问题描述

在自动化简历生成系统中，LLM 生成的内容存在以下严重问题：

### 1. 夸大其词
- **设计架构类**：
  - "设计并实现 Spring Boot 架构" → 实际只是使用 Spring Boot
  - "设计并实现分布式事务架构" → 实际只是使用分布式事务
  - "设计并实现分库分表架构" → 实际只是使用分库分表
  - "设计微服务架构" → 实际只是使用微服务

- **虚假数据**：
  - "提升系统性能 30%"
  - "提升查询速度 30%"
  - "节省资源占用 30%"
  - "提高用户体验度 20%"
  - "提高交易安全性 15%"
  - "节省开发时间 40 小时"
  - "降低人工成本 25%"

- **技术手段当业务功能**：
  - "支持分布式事务" → 这是技术手段，不是业务功能
  - "支持分库分表" → 这是技术手段，不是业务功能
  - "分布式锁保证一致性" → 这是技术手段，不是业务功能

### 2. 内容混淆
不同项目之间的内容互相混淆：
- **exc（引流权益兑换系统）** 出现了 naps 的 "收单结算模块：处理退款和换汇"
- **俄罗斯短剧项目** 出现了 naps 的 "收单结算模块"、"支付通道模块"
- **naps（全球收单）** 缺少 "商户管理"、"费率配置" 等后台管理功能

### 3. 与配置不符
项目配置中明确描述了业务功能，但生成的内容没有体现：

**exc 配置**：
```
description: "引流权益兑换系统，提供支付订单创建、退款、投诉等核心功能，
对接17+支付和广告平台。后台管理支持商户入驻、活动配置和广告位配置"
```

**实际生成的主要贡献**：
```
● 流量通道模块：广告投放和引流
● 支付通道模块：对接多个支付渠道
● 收单结算模块：处理退款和换汇  ← 这是 naps 的内容！
```

缺少：商户管理、活动配置、广告位配置

### 4. 产品描述问题
降级策略时，产品描述被技术栈覆盖：

**期望**：使用配置中的业务描述
**实际**：`"引流权益兑换系统项目，使用 Java, Boot, MySQL... 开发"`

## 当前技术方案

### 完整流程架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          简历生成完整流程                                    │
└─────────────────────────────────────────────────────────────────────────────┘

第一阶段：多项目并发处理（ThreadPoolExecutor，max_workers=3）
┌─────────────────────────────────────────────────────────────────────────────┐
│  项目 A                    项目 B                    项目 C                │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    │
│  │ 1. 获取 Commits  │    │ 1. 获取 Commits  │    │ 1. 获取 Commits  │    │
│  │    ├─ source 1   │    │    ├─ source 1   │    │    ├─ source 1   │    │
│  │    ├─ source 2   │    │    ├─ source 2   │    │    └─ source 2   │    │
│  │    └─ source 3   │    │    └─ source 3   │    │                   │    │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘    │
│           │                       │                       │               │
│           ▼                       ▼                       ▼               │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    │
│  │ 2. Commit 处理   │    │ 2. Commit 处理   │    │ 2. Commit 处理   │    │
│  │    Filter        │    │    Filter        │    │    Filter        │    │
│  │    ↓             │    │    ↓             │    │    ↓             │    │
│  │    Classifier    │    │    Classifier    │    │    Classifier    │    │
│  │    ↓             │    │    ↓             │    │    ↓             │    │
│  │    Splitter      │    │    Splitter      │    │    Splitter      │    │
│  │    ↓             │    │    ↓             │    │    ↓             │    │
│  │    Aggregator    │    │    Aggregator    │    │    Aggregator    │    │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘    │
│           │                       │                       │               │
│           ▼                       ▼                       ▼               │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    │
│  │ 3. LLM 生成      │    │ 3. LLM 生成      │    │ 3. LLM 生成      │    │
│  │    Project       │    │    Project       │    │    Project       │    │
│  │    Summarizer    │    │    Summarizer    │    │    Summarizer    │    │
│  │    (Agent)       │    │    (Agent)       │    │    (Agent)       │    │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘    │
│           │                       │                       │               │
│           ▼                       ▼                       ▼               │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    │
│  │ 4. Bullet 生成   │    │ 4. Bullet 生成   │    │ 4. Bullet 生成   │    │
│  │    Bullet        │    │    Bullet        │    │    Bullet        │    │
│  │    Generator     │    │    Generator     │    │    Generator     │    │
│  │    (Agent)       │    │    (Agent)       │    │    (Agent)       │    │
│  └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘    │
└───────────┼───────────────────────┼───────────────────────┼───────────────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    ▼
                    ┌───────────────────────────┐
                    │  收集所有项目结果          │
                    │  resume_projects[]        │
                    └───────────┬───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 第二阶段：公司经历生成（串行）                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                    ┌───────────────────────────┐
                    │ 按公司分组项目             │
                    │ company_groups = {        │
                    │   "zx": [exc, naps, ...], │
                    │   "other": [...]          │
                    │ }                         │
                    └───────────┬───────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌───────────┐   ┌───────────┐   ┌───────────┐
        │ 公司 zx   │   │ 公司 other│   │ ...       │
        │ ┌───────┐ │   │ ┌───────┐ │   │           │
        │ │ exc    │ │   │ │ ...    │ │   │           │
        │ │ naps   │ │   │ └───────┘ │   │           │
        │ │ drama  │ │   │           │   │           │
        │ └───────┘ │   │           │   │           │
        │     ↓     │   │     ↓     │   │     ↓     │
        │Company    │   │Company    │   │Company    │
        │Summarizer │   │Summarizer │   │Summarizer │
        │(Agent)    │   │(Agent)    │   │(Agent)    │
        └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
                  ┌───────────────────────┐
                  │ work_experiences[]    │
                  └───────────┬───────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 第三阶段：Word 文档生成                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                    ┌───────────────────────────┐
                    │ DocumentBuilder          │
                    │ .build_with_template()   │
                    │   ├─ work_experiences[]  │
                    │   └─ resume_projects[]   │
                    └───────────┬───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ resume_updated.docx   │
                    └───────────────────────┘
```

### Commit 处理详细流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      单个项目的 Commit 处理流程                               │
└─────────────────────────────────────────────────────────────────────────────┘

输入：project.sources = [
  {path: "C:/project/exc-adm", branch: "prd-ali"},
  {path: "C:/project/exc-pay", branch: "dev-complaint-ali"}
]

1. 获取 Commits (CommitFetcher)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ for source in sources:                                             │
   │   commits = fetcher.fetch(                                         │
   │     repo_path = source.path,                                       │
   │     branch = source.branch,                                        │
   │     author = "caihong <caihong@zxfintec.com>"                     │
   │   )                                                               │
   │   all_commits.extend(commits)                                     │
   │                                                                   │
   │ 输出示例：                                                         │
   │ [{                                                                │
   │   "hash": "abc123",                                              │
   │   "date": "2025-06-15 10:30:00",                                 │
   │   "message": "feat(payment): 支付订单创建功能\n\n- 实现订单创建接口│
   │                \n- 添加订单验证逻辑",                             │
   │   "author": "caihong"                                             │
   │ }, ...]                                                          │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
2. 过滤 Commits (CommitFilter)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ filter.filter_commits(all_commits)                                 │
   │                                                                   │
   │ 过滤规则：                                                         │
   │ - 过滤合并提交 (Merge commit)                                      │
   │ - 过滤 revert 提交                                                 │
   │ - 过滤空消息提交                                                   │
   │                                                                   │
   │ 输出：filtered_commits                                             │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
3. 分类 Commits (TaskClassifier)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ classifier.classify_commits(filtered_commits)                      │
   │                                                                   │
   │ 解析 Conventional Commits：                                         │
   │ - type: feat, fix, refactor, docs, style, test, chore              │
   │ - scope: payment, merchant, admin, etc.                            │
   │                                                                   │
   │ 输出示例：                                                         │
   │ [{                                                                │
   │   "type": "feat",                                                 │
   │   "scope": "payment",                                             │
   │   "message": "支付订单创建功能",                                    │
   │   "tasks": ["支付订单创建功能"],                                    │
   │   "original_message": "feat(payment): 支付订单创建功能"            │
   │ }, ...]                                                          │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
4. 拆分 Commits (CommitSplitter)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ splitter.split_commits(classified_commits, llm_client)             │
   │                                                                   │
   │ 拆分策略：                                                         │
   │ 1. Markdown 格式 (## 标题 + 1. 2. 编号)                            │
   │ 2. - 列表格式                                                     │
   │ 3. 普通文本分隔符 (，, and + 以及)                                │
   │ 4. LLM 兜底拆分（如果任务太长）                                    │
   │                                                                   │
   │ 输出示例：                                                         │
   │ [{                                                                │
   │   "type": "feat",                                                 │
   │   "scope": "payment",                                             │
   │   "tasks": [                                                      │
   │     "支付订单创建功能",                                             │
   │     "实现订单创建接口",                                             │
   │     "添加订单验证逻辑"                                              │
   │   ]                                                               │
   │ }, ...]                                                          │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
5. 聚合 Commits (CommitAggregator)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ aggregator.aggregate(split_commits, project_id="exc")              │
   │                                                                   │
   │ 聚合策略：                                                         │
   │ 按 type + scope 分组，合并相同 tasks，去重                          │
   │                                                                   │
   │ 输出示例：                                                         │
   │ [{                                                                │
   │   "type": "feat",                                                 │
   │   "scope": "payment",                                             │
   │   "tasks": [                                                      │
   │     "支付订单创建功能",                                             │
   │     "实现订单创建接口",                                             │
   │     "添加订单验证逻辑",                                             │
   │     "支付退款功能"  ← 来自另一个 commit                            │
   │   ],                                                              │
   │   "task_count": 4                                                 │
   │ },                                                                │
   │ {                                                                 │
   │   "type": "feat",                                                 │
   │   "scope": "merchant",                                            │
   │   "tasks": ["商户入驻功能", "商户配置管理"],                         │
   │   "task_count": 2                                                 │
   │ }, ...]                                                          │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
6. LLM 生成项目总结 (ProjectSummarizerAgent)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ agent = ProjectSummarizerAgent()  ← 每次创建新实例                  │
   │ summary = agent.summarize(aggregated_commits, project)             │
   │                                                                   │
   │ 输入：                                                             │
   │ - aggregated_commits: 聚合后的任务列表                             │
   │ - project: 项目配置（包含 description, tech_stack 等）              │
   │                                                                   │
   │ Prompt：                                                           │
   │ - 系统提示词：src/prompts/resume/project_summarizer.txt            │
   │ - 用户输入：聚合后的任务 + 项目配置                                │
   │                                                                   │
   │ 输出（ProjectSummary）：                                           │
   │ {                                                                 │
   │   "description": "引流权益兑换系统，提供支付订单创建、退款...",     │
   │   "technical_highlights": "使用 Java, Spring Boot, MySQL...",      │
   │   "key_achievements": [                                           │
   │     "对接17个支付渠道，实现多元化支付方式",                          │
   │     "开发商户管理功能，支持商户自主入驻"                            │
   │   ],                                                              │
   │   "main_contributions": [                                          │
   │     "支付通道模块：对接多个支付渠道",                               │
   │     "商户管理功能：支持商户入驻和配置"                              │
   │   ]                                                              │
   │ }                                                              │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
7. 后处理过滤 (_filter_achievements, _filter_contributions)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ 替换规则：                                                         │
   │ - "设计并实现 Spring Boot 架构" → "使用 Spring Boot"              │
   │ - "提升系统性能 30%" → "优化系统性能"                              │
   │ - "支撑高并发场景" → "处理高并发"                                  │
   │                                                                   │
   │ 项目间过滤：                                                       │
   │ - exc 项目：过滤 "收单结算"、"换汇"、"跨境支付"                    │
   │ - naps 项目：过滤 "广告"、"流量通道"                               │
   │                                                                   │
   │ 业务领域匹配：                                                     │
   │ - 如果项目没有广告，过滤 "广告"、"引流"、"流量通道"                │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
8. Bullet 生成 (BulletGeneratorAgent)
   ┌─────────────────────────────────────────────────────────────────────┐
   │ agent = BulletGeneratorAgent()  ← 每次创建新实例                   │
   │ bullets = agent.generate(                                       │
   │   summary=summary,                                               │
   │   claude_md=git_ctx.claude_md,  ← 从 Git 获取的文档              │
   │   readme=git_ctx.readme                                        │
   │ )                                                              │
   │                                                                 │
   │ 输入：                                                           │
   │ - summary: 项目总结（description, main_contributions 等）        │
   │ - claude_md: CLAUDE.md 内容                                     │
   │ - readme: README 内容                                           │
   │                                                                 │
   │ Prompt：                                                         │
   │ - 系统提示词：src/prompts/resume/bullet_generator.txt            │
   │                                                                 │
   │ 输出：简历格式的 bullet points                                   │
   └─────────────────────────────────────────────────────────────────────┘
```

### 公司经历生成详细流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      公司经历生成流程                                        │
└─────────────────────────────────────────────────────────────────────────────┘

输入：resume_projects = [
  {id: "exc", name: "引流权益兑换系统", company_id: "zx", ...},
  {id: "naps", name: "全球收单", company_id: "zx", ...},
  {id: "drama", name: "俄罗斯短剧项目", company_id: "zx", ...},
  {id: "chatppt", name: "ChatPPT", company_id: null, ...}
]

1. 按公司分组
   ┌─────────────────────────────────────────────────────────────────────┐
   │ company_groups = {}                                                │
   │ personal_projects = []                                             │
   │                                                                   │
   │ for project in resume_projects:                                   │
   │   if project.company_id:                                          │
   │     company_groups[project.company_id].append(project)           │
   │   else:                                                           │
   │     personal_projects.append(project)                             │
   │                                                                   │
   │ 结果：                                                             │
   │ company_groups = {                                                │
   │   "zx": [exc, naps, drama]  // 杭州碰呗网络科技有限公司的项目      │
   │ }                                                                │
   │ personal_projects = [chatppt]  // 个人项目                        │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
2. 为每个公司生成工作经历
   ┌─────────────────────────────────────────────────────────────────────┐
   │ for company_id, projects in company_groups.items():                │
   │                                                                 │
   │   # 获取公司信息                                                  │
   │   company_info = company_service.get_company_by_id(company_id)    │
   │   # {id: "zx", name: "杭州碰呗网络科技有限公司",                    │
   │   #  industry: "互联网", position: "java开发工程师"}                │
   │                                                                 │
   │   # 计算公司时间范围                                              │
   │   periods = [p.period for p in projects]  // 提取所有项目时间     │
   │   company_start = min(periods)  // 最早的项目开始时间              │
   │   company_end = max(periods)  // 最晚的项目结束时间                │
   │   company_period = f"{company_start}—{company_end}"                │
   │                                                                 │
   │   # 创建新的 agent 实例（避免上下文污染）                           │
   │   agent = CompanySummarizerAgent()                                 │
   │                                                                 │
   │   # 只传递属于该公司的项目                                         │
   │   work_experience = agent.generate_work_experience(               │
   │     company_info=company_info,                                     │
   │     projects=projects  // [exc, naps, drama]                       │
   │   )                                                               │
   │                                                                 │
   │   # agent 内部会提取每个项目的：                                   │
   │   # - main_contributions（主要贡献）                              │
   │   # - key_achievements（关键成果）                                 │
   │   # 然后汇总生成公司工作经历                                       │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
3. CompanySummarizerAgent 内部逻辑
   ┌─────────────────────────────────────────────────────────────────────┐
   │ def generate_work_experience(company_info, projects):              │
   │                                                                 │
   │   # 提取所有项目的主要贡献和关键成果                                │
   │   all_contributions = []                                           │
   │   all_achievements = []                                            │
   │                                                                 │
   │   for project in projects:                                         │
   │     all_contributions.extend(project.main_contributions)          │
   │     all_achievements.extend(project.key_achievements)             │
   │                                                                 │
   │   # 调用 LLM 生成公司工作经历                                      │
   │   prompt = f"""                                                    │
   │   基于公司信息和项目列表，生成工作经历：                            │
   │                                                                 │
   │   公司：{company_info['name']}                                     │
   │   行业：{company_info['industry']}                                 │
   │   职位：{company_info['position']}                                 │
   │                                                                 │
   │   项目：                                                           │
   │   {projects_info}                                                  │
   │                                                                 │
   │   生成主要职责（以 ● 开头）                                        │
   │   """                                                              │
   │                                                                 │
   │   response = llm_client.invoke(prompt)                             │
   │                                                                 │
   │   # 后处理：只保留以 ● 开头的行                                    │
   │   lines = response.split('\n')                                    │
   │   filtered = [line for line in lines if line.startswith('●')]     │
   │                                                                 │
   │   return '\n'.join(filtered)                                      │
   └─────────────────────────────────────────────────────────────────────┘
                               ↓
输出：work_experiences = [
  {
    "company_info": {id: "zx", name: "杭州碰呗网络科技有限公司", ...},
    "work_experience": "● 对接多个支付渠道\n● 支持会员订阅和支付...",
    "company_period": "2025/4—至今",
    "projects": ["exc", "naps", "drama"]
  }
]
```

### 上下文隔离策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        上下文隔离机制                                        │
└─────────────────────────────────────────────────────────────────────────────┘

问题：不同项目之间的 LLM 调用可能会互相干扰

解决方案：
1. 每个 ProjectSummarizerAgent 每次创建新实例
2. 每个 BulletGeneratorAgent 每次创建新实例
3. 每个 CompanySummarizerAgent 每次创建新实例
4. 使用独立的 LLM client 调用

代码示例：
┌─────────────────────────────────────────────────────────────────────┐
│ def process_single_project(project, idx):                           │
│     # 每次创建新的 agent 实例，确保没有历史上下文                    │
│     project_summarizer = ProjectSummarizerAgent()  # 新实例！        │
│     bullet_generator = BulletGeneratorAgent()      # 新实例！        │
│                                                                 │
│     summary = project_summarizer.summarize(aggregated_commits, ...) │
│     bullets = bullet_generator.generate(summary, ...)               │
│                                                                 │
│ for company_id, projects in company_groups.items():                │
│     # 每次创建新的 agent 实例，确保没有历史上下文                    │
│     company_summarizer = CompanySummarizerAgent()  # 新实例！        │
│                                                                 │
│     work_experience = company_summarizer.generate_work_experience(...)│
└─────────────────────────────────────────────────────────────────────┘

注意：虽然创建了新的 Agent 实例，但 LLM 模型本身是共享的（Ollama）
```

### 核心文件
- `src/core/agents/project_summarizer.py` - 项目总结 Agent
- `src/core/agents/bullet_generator.py` - Bullet 点生成 Agent
- `src/prompts/resume/project_summarizer.txt` - 项目总结 Prompt

### 后处理过滤逻辑（已实现）

#### 替换规则
```python
replacements = [
    (r'设计并实现\s+分库分表\s+架构', '使用分库分表'),
    (r'设计\s+Spring Boot\s+架构', '使用 Spring Boot'),
    (r'设计并实现\s+分布式事务\s+架构', '使用分布式事务'),
    (r'支撑高并发场景', '处理高并发'),
    (r'提升系统性能\s+\d+%', '优化系统性能'),
    (r'节省.*?资源占用\s+\d+', '降低资源占用'),
    # ... 更多规则
]
```

#### 项目间内容混淆过滤
```python
# exc 项目不应该有 naps 的内容
if 'exc' in project_name:
    if any(word in modified for word in ['收单结算', '换汇', '跨境支付']):
        continue  # 过滤
    if any(word in modified for word in ['支持分布式事务', '支持分库分表']):
        continue  # 过滤技术手段
```

#### 业务领域匹配
```python
# 如果项目没有广告，过滤掉广告相关内容
if not has_ad and any(word in modified for word in ['广告', '引流', '流量通道']):
    continue
```

### 降级策略（已实现）

当 LLM 生成失败时，使用基于规则的降级策略：

```python
# 根据项目名称智能生成主要贡献
if '俄罗斯短剧' in project_name:
    contributions.append("内容分发模块：支持内容分发功能")
    contributions.append("用户订阅模块：实现用户会员订阅管理功能")
    contributions.append("剧集管理模块：支持剧集上传和管理")
elif '全球收单' in project_name:
    contributions.append("支付通道模块：对接多个支付渠道")
    contributions.append("收单结算模块：处理跨境支付和结算")
    contributions.append("清结算模块：处理代付和清结算业务")
elif '引流权益兑换' in project_name:
    contributions.append("流量通道模块：广告投放和引流功能")
    contributions.append("支付通道模块：对接多个支付渠道")
    contributions.append("商户管理功能：支持商户入驻和配置")
```

## 技术约束

### 1. LLM 模型
- 使用 Ollama 本地部署的 Llama3.1:8b
- 无法使用 GPT-4 等更强的模型（公司内网环境）

### 2. 输入数据
- Git commits（通过 GitPython 获取）
- 项目配置（projects.json）
- CLAUDE.md / README 文档

### 3. 项目特点
- **多源项目**：一个项目可能包含多个 Git 仓库
- **并发处理**：使用 ThreadPoolExecutor 并发处理多个项目
- **上下文隔离**：每个项目使用独立的 Agent 实例

## 期望目标

### 内容要求
1. **不夸大**：不使用"设计架构"、"提升XX%"等夸大词汇
2. **准确**：内容必须与项目实际工作相符
3. **完整**：包含配置中描述的所有业务功能
4. **区分**：不同项目的内容不混淆

### 语言风格
- **使用**：开发、实现、对接、集成、处理
- **禁止**：设计架构、构建架构、支撑高并发、提升XX%

### 示例

#### ✅ 期望的输出
```
主要贡献：
● 支付通道模块：对接多个支付渠道
● 商户管理功能：支持商户入驻和配置
● 活动配置功能：支持广告位和活动配置

关键成果：
● 对接17个支付渠道，实现多元化支付方式
● 开发商户管理功能，支持商户自主入驻
● 实现活动配置功能，支持灵活的广告位配置
```

#### ❌ 当前的输出
```
主要贡献：
● 支付通道模块：对接多个支付渠道
● 收单结算模块：处理退款和换汇  ← 错误项目的内容

关键成果：
● 设计并实现支付模块对接多个支付渠道，支撑高并发场景  ← 夸大
● 优化缓存机制提升系统性能，节省 30% 资源占用  ← 虚假数据
● 实现商户管理功能支持入驻和配置，提高用户体验度 20%  ← 虚假数据
```

## 已尝试的解决方案

### 方案 A：改进 Prompt（效果有限）
在 prompt 中明确要求：
- 不使用"设计架构"、"构建架构"等词汇
- 不添加虚假的数据（如"提升30%"）
- 严格按照项目配置生成内容

**结果**：LLM 仍然会生成夸大内容

### 方案 B：后处理过滤（部分有效）
添加了大量替换规则和过滤逻辑：
- 替换夸大词汇
- 过滤虚假数字
- 过滤项目间混淆的内容

**结果**：
- 可以处理已知的夸大词汇
- 但 LLM 会换一种说法（如"构建核心模块" → "开发核心功能"）
- 需要不断添加新的替换规则

### 方案 C：降级策略（可靠但简单）
完全使用基于规则生成内容，不依赖 LLM

**结果**：
- 内容可靠，不夸大
- 但内容显得机械，缺乏个性化

## 待讨论的问题

### 核心问题
1. **如何让 LLM 生成不夸大、准确的内容？**
2. **如何避免项目间内容混淆？**
3. **如何确保生成的内容包含所有配置中的业务功能？**

### 可能的方向
1. **Prompt Engineering**：是否有更好的 prompt 设计方法？
2. **Few-shot Learning**：提供好的示例和坏的示例
3. **结构化输出**：强制 LLM 按照固定格式输出
4. **后处理增强**：更智能的后处理逻辑
5. **完全规则化**：放弃 LLM，使用模板 + 规则
6. **人工审核**：生成后人工审核修改

### 技术细节
1. **多源项目处理**：如何确保多个仓库的 commits 被正确聚合？
2. **上下文管理**：如何避免不同项目的上下文污染？
3. **业务功能识别**：如何从 commits 中提取业务功能？
4. **配置优先**：如何确保配置中的描述被优先使用？

## 相关代码片段

### 项目总结 Agent 调用流程
```python
# 1. 获取所有 commits
all_commits = []
for source in project.get("sources", []):
    commits = self.fetcher.fetch(
        repo_path=source.get("path"),
        branch=source.get("branch", "main"),
        author=self.config.get_author()
    )
    all_commits.extend(commits)

# 2. 过滤、分类、拆分、聚合
filtered_commits = self.filter.filter_commits(all_commits)
classified_commits = self.classifier.classify_commits(filtered_commits)
split_commits = self.splitter.split_commits(classified_commits, self.llm_client)
aggregated_commits = self.aggregator.aggregate(split_commits, project.get("id"))

# 3. LLM 生成
summary = project_summarizer.summarize(aggregated_commits, project)

# 4. 后处理过滤
# (在 _filter_achievements 和 _filter_contributions 中)
```

### 配置文件示例
```json
{
  "id": "exc",
  "name": "引流权益兑换系统",
  "description": "引流权益兑换系统，提供支付订单创建、退款、投诉等核心功能，
                 对接17+支付和广告平台。后台管理支持商户入驻、活动配置和广告位配置",
  "sources": [
    {"path": "C:\\Users\\sherry\\project\\exc-adm", "branch": "prd-ali"},
    {"path": "C:\\Users\\sherry\\project\\exc-pay", "branch": "dev-complaint-ali"}
  ],
  "tech_stack": ["Java", "Spring Boot", "MySQL", "Redis", "MyBatis", "RabbitMQ"],
  "highlights": [
    "对接17+支付和广告平台",
    "按周动态分表处理高并发"
  ]
}
```

## 请讨论

请基于以上信息，提供以下建议：

1. **如何改进 Prompt**，让 LLM 生成更准确的内容？
2. **是否有更好的架构设计**，避免当前的问题？
3. **如何平衡自动化和准确性**？
4. **是否有其他技术方案**可以考虑？
