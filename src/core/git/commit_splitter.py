"""Commit 拆分器 - 拆分为细粒度任务"""
import re
from pathlib import Path
from typing import List, Dict, Optional


class CommitSplitter:
    """Commit 拆分器 - 拆分为细粒度任务

    拆分优先级:
    1. Markdown 格式 (## 标题 + 1. 2. 编号)
    2. - 列表格式
    3. 普通文本分隔符 (， , and + 以及)
    4. LLM 兜底拆分
    """

    TEXT_SEPARATORS = ['，', ',', ' and ', '+', '以及']
    LLM_SPLIT_MIN_LENGTH = 15
    LLM_MAX_TASKS = 5

    # 清理模式：过滤 Co-Authored-By 签名、多余空白等
    COAUTHOR_PATTERN = re.compile(r'Co-Authored-By:.*?$', re.MULTILINE)
    TRAILING_SPACES_PATTERN = re.compile(r'\s+$')
    LEADING_JUNK_PATTERN = re.compile(r'^[\s\'"\(\)\'"，,\-\*]+')

    @classmethod
    def _read_prompt_template(cls, template_name: str) -> str:
        """读取 prompt 模板文件"""
        prompt_path = Path(__file__).parent.parent.parent / "prompts" / "common" / template_name
        if not prompt_path.exists():
            # 兼容旧路径
            old_path = Path(__file__).parent.parent.parent / "integrations" / "git_report" / "prompt" / template_name
            if old_path.exists():
                return old_path.read_text(encoding='utf-8')
            raise FileNotFoundError(f"Prompt 模板文件不存在: {prompt_path}")
        return prompt_path.read_text(encoding='utf-8')

    @classmethod
    def _clean_task(cls, task: str) -> Optional[str]:
        """清理单个任务文本"""
        if not task:
            return None

        # 移除 Co-Authored-By 签名
        task = cls.COAUTHOR_PATTERN.sub('', task)

        # 移除前后空白
        task = task.strip()

        # 移除开头的无效字符
        task = cls.LEADING_JUNK_PATTERN.sub('', task)

        # 过滤过短或无效的文本
        if len(task) < 2:
            return None

        return task

    @classmethod
    def _dedupe_tasks(cls, tasks: List[str]) -> List[str]:
        """去重并保持顺序"""
        seen = set()
        result = []
        for task in tasks:
            cleaned = cls._clean_task(task)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @classmethod
    def _split_markdown(cls, message: str) -> Optional[List[str]]:
        """拆分 Markdown 格式"""
        if "##" not in message:
            return None

        tasks = []
        blocks = message.split("##")

        for block in blocks:
            block = block.strip()
            if not block:
                continue
            numbered_items = re.split(r'\n\s*\d+[.、]\s*', block)
            for item in numbered_items:
                item = item.strip()
                if item and len(item) > 2:
                    tasks.append(item)

        return tasks if tasks else None

    @classmethod
    def _split_dash_list(cls, message: str) -> Optional[List[str]]:
        """拆分 - 列表格式"""
        lines = message.strip().split('\n')
        tasks = []

        for line in lines:
            line = line.strip()
            if line.startswith('- '):
                task = line[2:].strip()
                if task:
                    tasks.append(task)
            elif line.startswith('-'):
                task = line[1:].strip()
                if task:
                    tasks.append(task)

        return tasks if tasks else None

    @classmethod
    def _split_by_separators(cls, message: str) -> List[str]:
        """按分隔符拆分普通文本"""
        tasks = []
        lines = message.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue
            sep_pattern = '|'.join(re.escape(sep) for sep in cls.TEXT_SEPARATORS)
            parts = re.split(sep_pattern, line)
            for part in parts:
                part = part.strip()
                # 清理无效的分割结果
                cleaned = cls._clean_task(part)
                if cleaned:
                    tasks.append(cleaned)

        # 如果没有有效任务，尝试清理原始消息
        if not tasks:
            cleaned = cls._clean_task(message)
            if cleaned:
                return [cleaned]
            return []

        return tasks

    @classmethod
    def _count_sentences(cls, text: str) -> int:
        """统计句子数量"""
        sentences = re.split(r'[。.！!?？]', text)
        return len([s for s in sentences if s.strip()])

    @classmethod
    def split_by_llm(cls, message: str, llm_client=None) -> List[str]:
        """使用 LLM 拆分 commit"""
        if llm_client is None:
            return [message.strip()]

        # 读取 prompt 模板
        prompt_template = cls._read_prompt_template("split_commit_prompt.txt")
        prompt = prompt_template.format(max_tasks=cls.LLM_MAX_TASKS, message=message)

        try:
            response = llm_client.generate(prompt)
            tasks = [line.strip() for line in response.split('\n') if line.strip()]
            if len(tasks) > cls.LLM_MAX_TASKS:
                tasks = tasks[:cls.LLM_MAX_TASKS]
            if tasks:
                return tasks
            return [message.strip()]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"LLM 拆分失败: {e}")
            return [message.strip()]

    @classmethod
    def split(cls, classified_commit: Dict, llm_client=None) -> List[str]:
        """对分类后的 commit 进行拆分"""
        message = classified_commit.get('message', '')
        if not message:
            return []

        # 规则1: Markdown 格式
        markdown_tasks = cls._split_markdown(message)
        if markdown_tasks and len(markdown_tasks) > 1:
            return markdown_tasks

        # 规则2: - 列表
        dash_tasks = cls._split_dash_list(message)
        if dash_tasks and len(dash_tasks) > 1:
            return dash_tasks

        # 规则3: 分隔符
        separator_tasks = cls._split_by_separators(message)
        if len(separator_tasks) > 1:
            return separator_tasks

        # 规则4: LLM 兜底
        sentence_count = cls._count_sentences(message)
        message_length = len(message.strip())
        if sentence_count <= 1 and message_length > cls.LLM_SPLIT_MIN_LENGTH:
            return cls.split_by_llm(message, llm_client)

        return [message.strip()]

    @classmethod
    def split_commits(cls, classified_commits: List[Dict], llm_client=None) -> List[Dict]:
        """对分类后的 commit 列表进行拆分"""
        results = []
        for commit in classified_commits:
            # 保留原始 message 用于 source_commits
            original_message = commit.get('message', '').strip()
            # 移除 Co-Authored-By 签名
            original_message = cls.COAUTHOR_PATTERN.sub('', original_message).strip()

            tasks = cls.split(commit, llm_client)
            # 去重
            tasks = cls._dedupe_tasks(tasks)

            if tasks:  # 只保留有任务的 commit
                results.append({
                    'type': commit.get('type', 'refactor'),
                    'scope': commit.get('scope', 'default'),
                    'tasks': tasks,
                    'source_commit': commit.get('source_commit', ''),
                    'original_message': original_message
                })

        return results
