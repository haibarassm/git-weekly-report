"""Commit 处理模块 - 步骤4: 聚合"""
import re
from pathlib import Path
from typing import List, Dict
from collections import Counter


class TaskAggregator:
    """Task 聚合器 - 聚合为高层任务

    聚合策略:
    1. 按 type + scope 分组（基础聚合）
    2. 合并相同 tasks，去重
    3. 评分过滤（feat=3, fix=2, refactor=1，总分<2的过滤）
    4. LLM 语义聚合（生成高层摘要）
    """

    # 评分规则
    TYPE_SCORES = {
        'feature': 3,
        'fix': 2,
        'refactor': 1
    }
    MIN_SCORE = 2  # 最低分数要求

    # 状态关键词
    STATUS_KEYWORDS = {
        '已发布': ['发布', '上线'],
        '已提测': ['提测', '测试'],
        '对接中': ['开发', '实现', '添加', '新增'],
    }

    # 英文关键词提取模式（2个字符以上的单词）
    ENGLISH_PATTERN = re.compile(r'[a-zA-Z]{2,}')
    # 下划线命名模式（如 parent_code）
    UNDERSCORE_PATTERN = re.compile(r'[a-z]+_[a-z_]+')
    # 驼峰命名模式（如 parentCode）
    CAMEL_CASE_PATTERN = re.compile(r'[a-z]+[A-Z][a-zA-Z]*')

    # 环境名称（相对固定，用于过滤）
    # 中文环境名（直接替换）
    ENV_NAMES_CN = ['新加坡', '德国', '巴西']
    # 英文环境名（使用正则表达式确保单词边界匹配）
    ENV_NAMES_EN = ['SG', 'DE', 'BR', 'sg', 'de', 'br']
    ENV_PATTERNS_EN = [re.compile(rf'\b{re.escape(name)}\b') for name in ENV_NAMES_EN]

    # 通用中文技术关键词（不包含项目特定的）
    COMMON_TECH_KEYWORDS = {
        # 功能相关（通用）
        "登录", "权限", "菜单", "角色", "用户", "商户",
        "缓存", "数据库", "接口", "API", "功能", "模块",
        "配置", "设置", "参数",
        # 操作相关（通用）
        "修复", "优化", "添加", "新增", "删除", "修改", "更新",
        "实现", "重构", "调整", "改进", "完善",
        # 问题相关（通用）
        "问题", "bug", "错误", "异常", "故障",
        # 状态相关（通用）
        "发布", "上线", "提测", "测试", "部署",
    }

    # 删除/清理类关键词（用于识别低优先级内容）
    CLEANUP_KEYWORDS = ['删除', '移除', '清理', '移出']

    @classmethod
    def _read_prompt_template(cls, template_name: str) -> str:
        """读取 prompt 模板文件"""
        from pathlib import Path
        prompt_path = Path(__file__).parent.parent / "prompt" / template_name
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 模板文件不存在: {prompt_path}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    @classmethod
    def _detect_status(cls, tasks: List[str]) -> str:
        """从任务列表中识别状态"""
        for status, keywords in cls.STATUS_KEYWORDS.items():
            for task in tasks:
                for keyword in keywords:
                    if keyword in task:
                        return status
        return ''

    @classmethod
    def _filter_release_words(cls, text: str) -> str:
        """过滤发布相关词汇（环境词、部署操作词），保留核心功能词汇和状态词"""
        if not text:
            return text

        # 占位符列表（用于识别没有实际功能内容的情况）
        placeholders = ['xxx', '版本']
        status_words = ['发布', '上线', '提测', '测试']

        # 先检查原始文本：如果包含占位符，且移除占位符后只剩下环境名和状态词，则返回空
        has_placeholder = any(placeholder in text for placeholder in placeholders)
        if has_placeholder:
            temp_text = text
            for placeholder in placeholders:
                temp_text = temp_text.replace(placeholder, '')
            for env in cls.ENV_NAMES_CN + cls.ENV_NAMES_EN:
                temp_text = temp_text.replace(env, '')
            for deploy_word in ['合并', '环境']:
                temp_text = temp_text.replace(deploy_word, '')
            temp_text = ' '.join(temp_text.split())

            # 如果只有状态词，没有其他功能词，则返回空
            if temp_text in status_words:
                return ''

        # 正常过滤：移除各种词，但保留有效的状态词和功能词
        # 移除部署操作词
        for deploy_word in ['合并', '环境']:
            text = text.replace(deploy_word, ' ')
        # 移除环境名称
        for env in cls.ENV_NAMES_CN:
            text = text.replace(env, ' ')
        for env in cls.ENV_NAMES_EN:
            text = text.replace(env, ' ')
        # 移除占位符
        for placeholder in placeholders:
            text = text.replace(placeholder, ' ')

        # 清理多余空格
        text = ' '.join(text.split())

        return text.strip() if text else ''

    @classmethod
    def _generate_summary_with_status(cls, tasks: List[str], scope: str) -> str:
        """生成包含状态的摘要"""
        # 先识别状态（从原始 tasks 中）
        status = cls._detect_status(tasks)

        # 对于 release scope，如果没有检测到状态，默认为"已发布"
        if scope == 'release' and not status:
            status = '已发布'

        # 生成功能摘要
        function_summary = cls._generate_function_summary(tasks, scope)

        # 对于 release scope，进一步过滤环境词（但保留状态检测的上下文）
        if scope == 'release' and function_summary:
            function_summary = cls._filter_release_words(function_summary)

        # 如果过滤后为空，使用原始任务
        if not function_summary:
            function_summary = tasks[0][:20] if tasks else ''

        # 组合最终 summary
        if status and function_summary:
            return f"{function_summary}({status})"
        elif function_summary:
            return function_summary
        else:
            # fallback: 使用第一个任务
            return tasks[0][:30] if tasks else ''

    @classmethod
    def _generate_function_summary(cls, tasks: List[str], scope: str) -> str:
        """从任务列表生成核心功能摘要（rule-based fallback）"""
        if not tasks:
            return ''

        # 特殊处理：release scope 的任务
        if scope == 'release':
            # 提取核心功能名，过滤掉环境/状态信息
            core_parts = []
            for task in tasks:
                cleaned = cls._filter_release_words(task)
                # 只保留包含实际功能描述的词（不是纯状态词）
                if cleaned and cleaned not in ['发布', '上线', '提测', '测试'] and len(cleaned) >= 2:
                    core_parts.append(cleaned)

            # 如果提取到核心部分，取最短的核心作为功能名
            if core_parts:
                core_parts.sort(key=len)
                return core_parts[0][:20] if core_parts else tasks[0][:20]

        # 提取所有任务中共同的核心词
        all_keywords = []
        for task in tasks:
            keywords = cls._extract_keywords(task)
            all_keywords.extend(list(keywords))

        # 统计词频，找出最常见的核心词
        word_count = Counter(all_keywords)

        # 过滤掉通用词（操作类词）和过短的词
        generic_words = {'修复', '优化', '添加', '新增', '修改', '删除', '更新', '实现', 'null', 'sql', 'xml'}
        for word in list(word_count.keys()):
            if word in generic_words or len(word) < 3:
                del word_count[word]

        if word_count:
            # 优先查找包含技术关键词的组合
            tech_keywords_in_count = [w for w in word_count.keys() if '_' in w or any(c.isupper() for c in w)]
            if tech_keywords_in_count:
                # 有技术关键词，优先使用
                tech_word = tech_keywords_in_count[0]
                # 查找包含该技术关键词的原始任务，提取上下文
                for task in tasks:
                    if tech_word in task.lower():
                        # 提取技术关键词前后的简短上下文
                        idx = task.lower().find(tech_word)
                        context_start = max(0, idx - 6)
                        context_end = min(len(task), idx + len(tech_word) + 1)
                        context = task[context_start:context_end].strip()
                        # 清理操作词
                        for prefix in ['新增', '添加', '修复', '优化', '修改', '删除', '更新', '实现', '调整', '的', '将', '对']:
                            context = context.lstrip(prefix)
                        if context and len(context) >= len(tech_word):
                            return context[:20]
                # 如果找不到上下文，直接返回技术关键词
                return tech_word[:15]

            # 没有技术关键词，取最常见的2个词
            top_words = [w for w, _ in word_count.most_common(2)]
            summary = ' '.join(top_words)
            if len(summary) >= 2:
                return summary[:20]

        # fallback: 使用第一个任务，但优先保留技术关键词
        first_task = tasks[0]
        # 移除操作前缀
        for prefix in ['新增', '添加', '修复', '优化', '修改', '删除', '更新', '实现', '调整']:
            if first_task.startswith(prefix):
                first_task = first_task[len(prefix):]

        # 尝试提取技术关键词（驼峰、下划线命名）
        tech_keywords = []
        tech_keywords.extend(cls.UNDERSCORE_PATTERN.findall(first_task))
        tech_keywords.extend(cls.CAMEL_CASE_PATTERN.findall(first_task))

        # 如果找到技术关键词，优先使用
        if tech_keywords:
            # 取第一个技术关键词
            tech_keyword = tech_keywords[0].lower()
            # 如果还有空间，加上简短的上下文
            if len(first_task) > len(tech_keyword) + 2:
                # 提取技术关键词前的简短上下文（最多6个字）
                idx = first_task.lower().find(tech_keyword)
                if idx > 0:
                    context = first_task[max(0, idx - 6):idx].strip()
                    # 清理操作词和虚词
                    for cleanup_word in ['新增', '添加', '修复', '优化', '修改', '删除', '更新', '实现', '调整', '的', '将', '对']:
                        context = context.lstrip(cleanup_word)
                    if context:
                        return f"{context}{tech_keyword}"[:20]
            return tech_keyword[:15]

        return first_task[:15]

    @classmethod
    def _extract_keywords(cls, text: str) -> set[str]:
        """提取文本中的关键词（通用方法）"""
        keywords = set()

        # 提取英文单词（包括驼峰命名）
        english_words = cls.ENGLISH_PATTERN.findall(text)
        for word in english_words:
            if len(word) >= 2:
                keywords.add(word.lower())

        # 提取下划线命名的技术词（如 parent_code）
        underscore_words = cls.UNDERSCORE_PATTERN.findall(text)
        for word in underscore_words:
            keywords.add(word.lower())

        # 提取驼峰命名的技术词（如 parentCode）
        camel_case_words = cls.CAMEL_CASE_PATTERN.findall(text)
        for word in camel_case_words:
            keywords.add(word.lower())

        # 提取通用中文技术关键词
        for tech_keyword in cls.COMMON_TECH_KEYWORDS:
            if tech_keyword in text:
                keywords.add(tech_keyword)

        # 如果没有匹配到任何关键词，提取中文短语作为fallback
        if not keywords and text:
            # 提取中文短语（2-4个字）
            chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
            if len(chinese_chars) >= 2:
                fallback = ''.join(chinese_chars[:4])
                keywords.add(fallback)

        return keywords

    @classmethod
    def _compute_similarity(cls, keywords1: set[str], keywords2: set[str]) -> float:
        """计算关键词相似度（Jaccard 系数）"""
        if not keywords1 or not keywords2:
            return 0.0
        intersection = keywords1 & keywords2
        union = keywords1 | keywords2
        return len(intersection) / len(union) if union else 0.0

    @classmethod
    def _group_by_type_scope(cls, split_commits: List[Dict]) -> Dict[str, List[Dict]]:
        """按 type + scope 分组"""
        groups = {}
        for commit in split_commits:
            key = f"{commit.get('type', 'refactor')}/{commit.get('scope', 'default')}"
            if key not in groups:
                groups[key] = []
            groups[key].append(commit)
        return groups

    @classmethod
    def _format_commit_title(cls, commit_type: str, scope: str, original_message: str) -> str:
        """构造格式化的 commit 标题"""
        # 格式: [type(scope): message]
        return f"[{commit_type}({scope}): {original_message}]"

    @classmethod
    def _cluster_by_keywords(cls, split_commits: List[Dict]) -> List[Dict]:
        """关键词相似度聚类"""
        import logging
        logger = logging.getLogger(__name__)

        # 步骤1: 按 type + scope 分组
        type_scope_groups = cls._group_by_type_scope(split_commits)
        logger.debug(f"  分组详情: {list(type_scope_groups.keys())}")

        aggregated = []

        for group_key, commits in type_scope_groups.items():
            commit_type, scope = group_key.split('/', 1)

            # 步骤2: 提取所有tasks及其关键词和原始message
            all_tasks = []
            for commit in commits:
                # 获取原始消息（优先使用 original_message，其次 message，最后 source_commit）
                original_message = commit.get('original_message', commit.get('message', commit.get('source_commit', '')))
                # 构造格式化的 commit 标题
                commit_title = cls._format_commit_title(commit_type, scope, original_message)
                for task in commit.get('tasks', []):
                    keywords = cls._extract_keywords(task)
                    all_tasks.append({
                        'task': task,
                        'keywords': keywords,
                        'commit_title': commit_title
                    })

            logger.info(f"  [{commit_type}/{scope}] 提取 {len(all_tasks)} 个任务")
            for i, t in enumerate(all_tasks):
                logger.info(f"    任务{i+1}: {t['task'][:30]}... (来源: {t['commit_title'][:40]}...)")

            # 步骤3: 聚类（贪心算法）
            clusters = []
            used_indices = set()

            for i, task_item in enumerate(all_tasks):
                if i in used_indices:
                    continue

                # 创建新簇
                cluster = {
                    'tasks': [task_item['task']],
                    'source_commits': [task_item['commit_title']],
                    'keywords': task_item['keywords']
                }
                used_indices.add(i)

                # 查找相似任务
                for j, other_item in enumerate(all_tasks):
                    if j in used_indices or j == i:
                        continue

                    similarity = cls._compute_similarity(
                        cluster['keywords'],
                        other_item['keywords']
                    )

                    # 相似度阈值: 0.25（可调）
                    if similarity >= 0.25:
                        cluster['tasks'].append(other_item['task'])
                        if other_item['commit_title'] not in cluster['source_commits']:
                            cluster['source_commits'].append(other_item['commit_title'])
                        cluster['keywords'] |= other_item['keywords']
                        used_indices.add(j)

                clusters.append(cluster)

            logger.info(f"  [{commit_type}/{scope}] 聚类为 {len(clusters)} 个组")
            for i, cluster in enumerate(clusters):
                logger.info(f"    组{i+1}: {len(cluster['tasks'])} 个任务, {cluster['tasks']}")

            # 步骤4: 生成聚合结果
            for cluster in clusters:
                # 生成功能摘要（包含状态检测）
                summary = cls._generate_summary_with_status(cluster['tasks'], scope)

                # 对于 release scope，清理 tasks 中的环境词
                cleaned_tasks = cluster['tasks']
                if scope == 'release':
                    cleaned_tasks = [cls._filter_release_words(task) for task in cluster['tasks']]
                    cleaned_tasks = [t for t in cleaned_tasks if t]  # 过滤空字符串

                aggregated.append({
                    'type': commit_type,
                    'scope': scope,
                    'summary': summary,
                    'tasks': cleaned_tasks,
                    'source_commits': cluster['source_commits'],
                    'task_count': len(cleaned_tasks)
                })

        return aggregated

    @classmethod
    def _merge_and_dedupe(cls, clustered: List[Dict]) -> List[Dict]:
        """合并相同的 summary 和 tasks，去重"""
        import logging
        logger = logging.getLogger(__name__)

        # 按 type + scope 分组（避免不同 type 混在一起）
        type_scope_groups = {}
        for item in clustered:
            key = f"{item.get('type', 'refactor')}/{item.get('scope', 'default')}"
            if key not in type_scope_groups:
                type_scope_groups[key] = []
            type_scope_groups[key].append(item)

        logger.info(f"  按 type+scope 分组: {[(key, len(items)) for key, items in type_scope_groups.items()]}")

        merged = []
        for key, items in type_scope_groups.items():
            commit_type, scope = key.split('/', 1)
            logger.info(f">>> [{commit_type}/{scope}] 开始合并 {len(items)} 个聚合组")

            # 合并相同的 tasks
            task_set = set()
            merged_tasks = []
            source_commits = []
            duplicate_tasks = []  # 记录被去重的任务
            duplicate_sources = []  # 记录被去重的 source_commits

            for item in items:
                for task in item.get('tasks', []):
                    if task not in task_set:
                        task_set.add(task)
                        merged_tasks.append(task)
                    else:
                        duplicate_tasks.append(task)
                source_commits.extend(item.get('source_commits', []))

            # 去重 source_commits
            unique_source_commits = []
            seen_sources = set()
            for src in source_commits:
                if src not in seen_sources:
                    seen_sources.add(src)
                    unique_source_commits.append(src)
                else:
                    duplicate_sources.append(src)

            # 详细日志
            if duplicate_tasks:
                logger.info(f"  被去重的任务: {duplicate_tasks}")
            if duplicate_sources:
                logger.info(f"  被去重的 source_commits: {duplicate_sources}")
            logger.info(f"  任务: {len(task_set) + len(duplicate_tasks)} -> {len(merged_tasks)} (去重 {len(duplicate_tasks)} 个)")
            logger.info(f"  source_commits: {len(source_commits)} -> {len(unique_source_commits)} (去重 {len(duplicate_sources)} 个)")

            # 生成包含状态的摘要
            summary = cls._generate_summary_with_status(merged_tasks, scope)

            merged_item = {
                'type': commit_type,
                'scope': scope,
                'summary': summary,
                'tasks': merged_tasks,
                'source_commits': unique_source_commits,
                'task_count': len(merged_tasks)
            }
            merged.append(merged_item)
            logger.info(f"  [{commit_type}/{scope}] 合并后: {len(items)} 个聚合组 -> {len(merged_tasks)} 个任务 -> {summary}")

        return merged

    @classmethod
    def _filter_by_score(cls, items: List[Dict]) -> List[Dict]:
        """根据评分过滤，剔除总分 < 2 的组"""
        import logging
        logger = logging.getLogger(__name__)

        filtered = []
        filtered_out = []

        for item in items:
            commit_type = item.get('type', 'refactor')
            scope = item.get('scope', 'default')
            task_count = item.get('task_count', 0)
            summary = item.get('summary', '')[:30]
            tasks = item.get('tasks', [])
            source_commits = item.get('source_commits', [])

            # 统计删除类任务数量
            cleanup_count = sum(1 for task in tasks if any(kw in task for kw in cls.CLEANUP_KEYWORDS))
            non_cleanup_count = task_count - cleanup_count

            # 如果全是删除类任务，直接过滤掉
            if cleanup_count == task_count and task_count > 0:
                filtered_out.append({
                    'type': commit_type,
                    'scope': scope,
                    'score': 0,
                    'summary': summary,
                    'tasks': tasks,
                    'source_commits': source_commits
                })
                logger.info(f"  [过滤-全是删除] {commit_type}/{scope} - {summary}")
                logger.info(f"    任务列表: {tasks}")
                continue

            # 计算得分：非删除类任务按正常评分，删除类任务每个只算1分
            score = cls.TYPE_SCORES.get(commit_type, 1) * non_cleanup_count + cleanup_count

            if score >= cls.MIN_SCORE:
                item['score'] = score
                filtered.append(item)
                logger.info(f"  [保留] {commit_type}/{scope} 得分:{score} (tasks:{task_count}, cleanup:{cleanup_count}) - {summary}")
                logger.info(f"    任务列表: {tasks}")
                logger.info(f"    来源: {source_commits}")
            else:
                filtered_out.append({
                    'type': commit_type,
                    'scope': scope,
                    'score': score,
                    'summary': summary,
                    'tasks': tasks,
                    'source_commits': source_commits
                })
                logger.info(f"  [过滤] {commit_type}/{scope} 得分:{score} < {cls.MIN_SCORE} - {summary}")
                logger.info(f"    任务列表: {tasks}")
                logger.info(f"    来源: {source_commits}")

        logger.info(f"  评分过滤结果: 保留 {len(filtered)} 个，过滤 {len(filtered_out)} 个")
        if filtered_out:
            logger.info(f"  过滤详情: {filtered_out}")

        return filtered

    @classmethod
    def _clean_summary(cls, text: str) -> str:
        """清理 LLM 输出中的包裹符号和多余标点"""
        if not text:
            return text

        # 去掉首尾引号（中英文）
        while text and text[0] in ('"', '\u201c', '\u300c', '\u300e', '\uff08'):
            text = text[1:]
        while text and text[-1] in ('"', '\u201d', '\u300d', '\u300f', '\uff09'):
            # 保留末尾的 (状态) 括号
            if text[-1] == '\uff09' and '(' in text:
                break
            if text[-1] == ')' and '(' in text:
                break
            text = text[:-1]

        # 去掉首尾书名号
        while text and text[0] in ('\u300a', '\u300e'):
            text = text[1:]
        while text and text[-1] in ('\u300b', '\u300f'):
            text = text[:-1]

        # 去掉末尾句号
        text = text.rstrip('。.')

        return text.strip()

    @classmethod
    def _generate_summary(cls, aggregated: List[Dict], llm_client=None) -> List[Dict]:
        """使用 LLM 生成高层摘要"""
        if llm_client is None:
            return aggregated

        import logging
        logger = logging.getLogger(__name__)

        results = []
        for item in aggregated:
            # 获取 commit titles
            commit_titles = item.get('source_commits', [])
            titles_text = '\n'.join(f"- {title}" for title in commit_titles[:3])  # 最多显示3个

            tasks_text = '\n'.join(f"- {task}" for task in item.get('tasks', []))

            input_info = f"""类型: {item.get('type')}/{item.get('scope')}
Commits:
{titles_text}
任务:
{tasks_text}"""

            # 读取 prompt 模板
            prompt_template = cls._read_prompt_template("generate_summary_prompt.txt")
            if prompt_template:
                prompt = prompt_template.format(input_info=input_info)
            else:
                # fallback: 如果模板文件不存在，使用硬编码的 prompt
                prompt = f"""请根据以下 commit 标题和任务列表生成一个简洁的摘要（最多15个字）。

{input_info}

要求：
1. 摘要应反映这些任务的共同主题或核心功能
2. 使用简洁的中文描述
3. 对于发布类 commits，必须移除所有环境词（新加坡/德国/巴西/SG/DE/BR等）
4. 如果检测到状态（已发布/已提测/对接中），请在摘要末尾加上(状态)
5. 只返回摘要，不要其他内容

重要：不要包含任何环境名称！

摘要："""

            logger.info(f">>> [LLM 摘要生成] 输入:\n{input_info}")

            try:
                llm_summary = llm_client.generate(prompt).strip()
                logger.info(f">>> [LLM 原始输出] {llm_summary}")

                # 清理 LLM 输出中的包裹符号
                llm_summary = cls._clean_summary(llm_summary)

                # 如果 LLM 摘要太短（<3字），使用第一个任务作为兜底
                if len(llm_summary) < 3 and item.get('tasks'):
                    llm_summary = item['tasks'][0][:15]
                    logger.warning(f"LLM 摘要太短，使用任务兜底: {llm_summary}")

                # 如果 LLM 没有包含状态，我们手动检测并添加
                status = cls._detect_status(item.get('tasks', []))
                if status and f"({status})" not in llm_summary:
                    summary = f"{llm_summary}({status})"
                else:
                    summary = llm_summary

                # 如果是 release scope，确保过滤了环境词
                if item.get('scope') == 'release':
                    summary = cls._filter_release_words(summary)

                logger.info(f">>> [LLM 摘要生成] 最终输出: {summary}")
                item['summary'] = summary
            except Exception as e:
                logger.warning(f"LLM 摘要生成失败: {e}，使用 rule-based 摘要")
                # 保留原有摘要

            results.append(item)

        return results

    @classmethod
    def aggregate(cls, split_commits: List[Dict], llm_client=None) -> List[Dict]:
        """聚合已拆分的 commits

        Args:
            split_commits: V0.3 拆分后的 commit 列表
            llm_client: LLM 客户端（可选，用于生成摘要）

        Returns:
            聚合后的任务列表，结构:
            [
                {
                    "type": "fix",
                    "scope": "perms",
                    "summary": "权限管理优化",
                    "tasks": ["修复菜单权限", "优化角色权限"],
                    "source_commits": ["原始commit消息1", "原始commit消息2"],
                    "task_count": 2,
                    "score": 4
                },
                ...
            ]
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f">>> [V0.4 聚合步骤1] 按 type+scope 分组并聚类")

        # 步骤1: 按 type + scope 分组，关键词聚类
        clustered = cls._cluster_by_keywords(split_commits)
        logger.info(f"  聚类结果: {len(split_commits)} 个 commit -> {len(clustered)} 个聚合组")

        logger.info(f">>> [V0.4 聚合步骤2] 合并去重")

        # 步骤2: 合并相同的 tasks，去重
        merged = cls._merge_and_dedupe(clustered)

        logger.info(f">>> [V0.4 聚合步骤3] 评分过滤")

        # 步骤3: 评分过滤
        filtered = cls._filter_by_score(merged)

        logger.info(f">>> [V0.4 聚合步骤4] 生成摘要")

        # 步骤4: LLM 生成摘要
        with_summary = cls._generate_summary(filtered, llm_client)

        return with_summary
