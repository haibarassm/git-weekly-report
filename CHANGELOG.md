# CHANGELOG

## [v0.4] - 2026-04-07

### ✨ 新功能

- feat: V0.4 添加 Task 聚合功能
- feat: 模块重构为步骤化结构（filter_classifier, splitter, aggregator）
- feat: 关键词相似度聚类（Jaccard 系数）
- feat: 通用关键词提取（英文单词、下划线命名、驼峰命名）
- feat: 环境词过滤（新加坡、德国、巴西、SG、DE、BR）
- feat: 状态检测（已发布/已提测/对接中）
- feat: 评分过滤（feature=3, fix=2, refactor=1, 最低分=2）
- feat: 全删除类任务直接过滤
- feat: release scope tasks 环境词清理

### 🐛 问题修复

- fix: 修复摘要生成关键词拼接问题（改用空格分隔）
- fix: 修复 type+scope 分组合并问题（避免不同 type 混在一起）
- fix: 修复删除类内容评分问题（只降低删除类任务权重）
- fix: 清理列表符号（-, *）

### 📝 文档

- docs: 更新 README 添加 V0.4 功能说明

### ✅ 测试

- test: 添加 TaskAggregator 测试用例
- test: 总计 98 个测试用例全部通过

## [v0.3] - 2026-04-02

### ✨ 新功能

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

- docs: 添加 CHANGELOG for V0.2
- docs: 更新 README 添加 V0.2 功能说明

### ✅ 测试

- test: 添加 ReportApp 边界测试用例 (V0.2)

### 🔧 其他

- debug: 添加更详细的调试日志
- config: 添加Docker环境api_base配置说明
- Initial commit: Git Weekly Report Generator v0.1

