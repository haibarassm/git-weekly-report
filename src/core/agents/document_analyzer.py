"""文档分析 Agent - 自动提取项目信息"""
from pathlib import Path
from typing import List, Dict
import logging
import json

from src.core.llm.client import get_llm_client


class DocumentAnalyzerAgent:
    """分析项目文档，自动提取项目信息

    从上传的文档（claude.md、README 等）中提取：
    - 项目描述
    - 技术栈
    - 项目亮点
    """

    PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "resume" / "document_analyzer.txt"

    def __init__(self):
        self.llm = get_llm_client()
        self._load_prompt()

    def _load_prompt(self):
        """加载提示词模板"""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"提示词文件不存在: {self.PROMPT_PATH}")
        self._prompt = self.PROMPT_PATH.read_text(encoding='utf-8')

    def analyze(self, documents: Dict, repo_path: str = None) -> Dict:
        """分析文档，提取项目信息

        Args:
            documents: 文档内容字典 {filename: content}
            repo_path: 仓库路径（可选，用于读取 README）

        Returns:
            {
                "description": "项目描述",
                "tech_stack": ["技术1", "技术2"],
                "highlights": ["亮点1", "亮点2"]
            }
        """
        logger = logging.getLogger(__name__)

        # 验证输入
        if not documents:
            logger.warning("文档内容为空，返回默认值")
            return {"description": "", "tech_stack": [], "highlights": []}

        # 打印文档信息用于调试
        doc_names = list(documents.keys())
        logger.info(f">>> [文档分析] 开始，共 {len(documents)} 个文档: {doc_names}")

        for name, content in documents.items():
            logger.info(f"  - {name}: {len(content)} 字符")
            # 检查是否是文件路径而不是内容
            if len(content) < 200 and '\\' in content and ':' in content:
                logger.warning(f"⚠️ 文档内容看起来像文件路径而不是实际内容!")

        # 构建上下文
        context = self._build_context(documents)
        logger.info(f">>> [文档分析] 构建的上下文长度: {len(context)} 字符")
        logger.info(f">>> [文档分析] 上下文预览: {context[:300]}...")

        # 调用 LLM（使用 replace 而不是 format 避免 JSON 中的花括号问题）
        try:
            prompt = self._prompt.replace("{context}", context)
            response = self.llm.generate(prompt)
            logger.info(f">>> [文档分析] LLM 原始响应: {response[:300]}...")
            result = self._parse_response(response)

            # 补充技术栈：从原始文档中提取 LLM 可能遗漏的技术
            result = self._supplement_tech_stack(result, documents)

            logger.info(f">>> [文档分析] 完成: description={result.get('description', '')[:50]}..., tech_stack={result.get('tech_stack', [])}, highlights={len(result.get('highlights', []))} 条")
            return result
        except Exception as e:
            logger.warning(f"文档分析失败: {e}，使用规则提取", exc_info=True)
            return self._fallback_analyze(documents)

    def _build_context(self, documents: List[str]) -> str:
        """构建 LLM 输入"""
        logger = logging.getLogger(__name__)
        parts = []

        for filename, content in documents.items():
            # 移除 "Claude Code guidance" 部分
            processed_content = content

            # 查找并移除 "This file provides guidance to Claude Code" 相关内容
            claude_guidance_markers = [
                "This file provides guidance to Claude Code",
                "# CLAUDE.md",
                "This file provides guidance",
                "## Project Ecosystem Overview"
            ]

            for marker in claude_guidance_markers:
                if marker in processed_content:
                    # 找到这个标记的位置
                    idx = processed_content.find(marker)
                    if idx == 0:  # 如果在开头，跳过整个这一段
                        # 查找下一个主要标题
                        next_marker = processed_content.find("\n## ", idx + 10)
                        if next_marker > 0:
                            processed_content = processed_content[next_marker:]
                        else:
                            # 没找到其他标题，保留全部
                            pass
                    break

            # 限制单文档长度
            max_doc_length = 5000
            if len(processed_content) > max_doc_length:
                processed_content = processed_content[:max_doc_length] + "\n...(内容已截断)"

            parts.append(f"## {filename}")
            parts.append(processed_content)

        context = "\n\n".join(parts)
        logger.info(f"构建上下文完成: 总长度 {len(context)} 字符, 包含 {len(documents)} 个文档")

        return context

    def _parse_response(self, response: str) -> Dict:
        """解析 LLM 响应"""
        logger = logging.getLogger(__name__)

        # 清理响应
        response = response.strip()

        # 移除可能的 markdown 代码块标记
        response = response.replace('```json', '').replace('```', '')

        # 查找 JSON 对象的起始位置
        json_start = response.find('{')

        if json_start < 0:
            logger.warning("未找到 JSON 起始位置")
            logger.info("降级使用文本解析")
            return self._parse_text_response(response)

        # 从起始位置开始，匹配括号找到 JSON 结束位置
        brace_count = 0
        json_end = -1
        for i in range(json_start, len(response)):
            if response[i] == '{':
                brace_count += 1
            elif response[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i
                    break

        if json_end < 0:
            logger.warning("未找到 JSON 结束位置，尝试使用最后一个 }")
            json_end = response.rfind('}')

        if json_end < 0 or json_end <= json_start:
            logger.warning("无法定位 JSON 对象")
            logger.info("降级使用文本解析")
            return self._parse_text_response(response)

        json_str = response[json_start:json_end + 1]
        logger.info(f"提取的 JSON 字符串长度: {len(json_str)}")
        logger.info(f"提取的 JSON 字符串预览: {json_str[:200]}...")

        try:
            data = json.loads(json_str)
            result = {
                "description": data.get("description", ""),
                "tech_stack": data.get("tech_stack", []),
                "highlights": data.get("highlights", [])
            }
            logger.info(f"JSON 解析成功!")
            desc_preview = result['description'][:50] if result['description'] else '(empty)'
            logger.info(f"  description: {desc_preview}")
            logger.info(f"  tech_stack: {len(result['tech_stack'])} 项")
            logger.info(f"  highlights: {len(result['highlights'])} 条")
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")
            logger.info(f"JSON 字符串前 300 字符: {json_str[:300]}")
            logger.info("降级使用文本解析")
            return self._parse_text_response(response)

    def _parse_text_response(self, response: str) -> Dict:
        """解析文本格式响应"""
        lines = response.split('\n')

        result = {
            "description": "",
            "tech_stack": [],
            "highlights": []
        }

        current_section = None
        for line in lines:
            original_line = line
            line = line.strip()

            # 识别章节标题（支持 **title**: content 格式）
            if "**description**" in line.lower():
                current_section = "desc"
                # 如果同一行有内容，提取出来
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1 and parts[1].strip():
                        result["description"] = parts[1].strip() + " "
                continue
            elif "项目描述" in line or line.lower().startswith("description:"):
                current_section = "desc"
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) > 1 and parts[1].strip():
                        result["description"] = parts[1].strip() + " "
                continue
            elif "**tech_stack**" in line.lower():
                current_section = "tech"
                continue
            elif "技术栈" in line or line.lower().startswith("tech_stack:"):
                current_section = "tech"
                continue
            elif "**highlights**" in line.lower():
                current_section = "high"
                continue
            elif "项目亮点" in line or line.lower().startswith("highlights:"):
                current_section = "high"
                continue
            elif "项目结构" in line or (line.startswith("**") and "技术" not in line and "亮点" not in line and "描述" not in line):
                # 跳过项目结构和其他非目标章节
                if "技术栈" not in line and "highlights" not in line and "description" not in line:
                    current_section = None
                continue

            if not line:
                continue

            # 解析描述
            if current_section == "desc":
                # 描述通常是普通文本，不是列表项
                if not line.startswith(('-', '•', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                    result["description"] += line + " "

            # 解析技术栈 - 支持多种列表格式
            elif current_section == "tech":
                # 移除列表标记
                clean_line = line
                if clean_line.startswith('- '):
                    clean_line = clean_line[2:].strip()
                elif clean_line.startswith('•'):
                    clean_line = clean_line[1:].strip()
                elif clean_line.startswith('* '):
                    clean_line = clean_line[2:].strip()
                elif clean_line.startswith('*'):
                    clean_line = clean_line[1:].strip()

                # 过滤掉目录路径和章节标题
                if clean_line and not clean_line.startswith('**') and not '/' in clean_line and not clean_line.endswith(':'):
                    result["tech_stack"].append(clean_line)

            # 解析亮点 - 支持带数字或符号的列表
            elif current_section == "high":
                # 移除各种列表标记
                clean_line = line
                if clean_line.startswith('- '):
                    clean_line = clean_line[2:].strip()
                elif clean_line.startswith('•'):
                    clean_line = clean_line[1:].strip()
                elif clean_line.startswith('* '):
                    clean_line = clean_line[2:].strip()
                elif clean_line.startswith('*'):
                    clean_line = clean_line[1:].strip()
                else:
                    # 移除数字标记（如 "1. " 或 "1、"）
                    import re
                    clean_line = re.sub(r'^\d+[\.\、]\s*', '', clean_line).strip()

                # 过滤掉章节标题、空行和说明文字
                if clean_line and not clean_line.startswith('**') and not clean_line.endswith(':') and not clean_line.startswith('请注意') and not clean_line.startswith('以上信息') and not clean_line.startswith('根据提供的'):
                    result["highlights"].append(clean_line)

        logger.info(f"文本解析结果: description={result.get('description', '')[:30] if result.get('description') else '(empty)'}, tech_stack={len(result.get('tech_stack', []))} 项, highlights={len(result.get('highlights', []))} 条")
        return result

    def _supplement_tech_stack(self, result: Dict, documents: Dict) -> Dict:
        """补充技术栈：从原始文档中提取 LLM 可能遗漏的技术"""
        logger = logging.getLogger(__name__)

        # 核心技术关键词（按优先级排序）
        core_tech = {
            # 编程语言
            'Java', 'Python', 'Go', 'JavaScript', 'TypeScript', 'C++', 'C#',
            # 核心框架
            'Spring Boot', 'Spring Cloud', 'Spring Cloud Alibaba', 'Django', 'Flask', 'FastAPI',
            'React', 'Vue', 'Angular', 'Node.js',
            # 数据访问
            'MyBatis-Plus', 'MyBatis', 'JPA', 'Hibernate',
            # 数据库
            'MySQL', 'PostgreSQL', 'MongoDB', 'Oracle',
            # 中间件/缓存
            'Redis', 'RabbitMQ', 'Kafka', 'Elasticsearch', 'ZooKeeper',
            # 分库分表/分布式
            'ShardingSphere', 'Seata', 'Redisson', 'Dubbo', 'Nacos',
            # 连接池
            'Druid', 'HikariCP',
            # 工具库（只保留重要的）
            'Hutool', 'FastJSON', 'Gson', 'Jackson',
            # 容器化
            'Docker', 'Kubernetes'
        }

        # 亮点到核心技术的映射
        highlight_tech_mapping = {
            '分库分表': ['ShardingSphere', 'MyBatis-Plus'],
            '分布式事务': ['Seata'],
            '分布式锁': ['Redisson'],
            '消息队列': ['RabbitMQ', 'Kafka'],
            '异步': ['RabbitMQ', 'Kafka'],
            '缓存': ['Redis'],
            '微服务': ['Spring Cloud', 'Spring Cloud Alibaba', 'Nacos', 'Dubbo']
        }

        # 合并所有文档内容
        all_content = "\n".join(documents.values()).lower()

        # 清理技术栈：移除版本号、详细描述
        def clean_tech(tech):
            """清理技术名称，移除版本号和额外描述"""
            import re
            # 移除版本号（如 3.1.12, 3.x, 3.41.0）
            tech = re.sub(r'\s+\d+(\.\d+)*\.?\d*', '', tech)  # "Spring Boot 3.1.12" → "Spring Boot"
            tech = re.sub(r'\s+\.?\d+\.?x\s*', '', tech)  # "Spring Boot .x" → "Spring Boot"
            # 移除括号内容
            tech = re.sub(r'\s*\([^)]*\)', '', tech)
            # 将 "via" 和 "+" 转换为空格，准备拆分
            tech = re.sub(r'\s*\+\s*', ' ', tech)  # "Redis + Redisson" → "Redis Redisson"
            tech = re.sub(r'\s*via\s*', ' ', tech)  # "MySQL via ShardingSphere" → "MySQL ShardingSphere"
            # 移除其他描述词
            tech = re.sub(r'\s*(with|queues?|mechanism)\s*', ' ', tech)  # "RabbitMQ (11 queues)" → "RabbitMQ"
            # 清理多余空格
            tech = ' '.join(tech.split())
            return tech

        # 清理并拆分技术栈
        def clean_and_split_tech(tech):
            """清理技术名称，并拆分合并的技术"""
            cleaned = clean_tech(tech)

            # 定义核心技术列表（用于识别）
            core_technologies = {
                'Java', 'Python', 'Go', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Rust', 'Kotlin',
                'Spring', 'Spring', 'Boot', 'Spring', 'Cloud', 'Alibaba',
                'MySQL', 'PostgreSQL', 'MongoDB', 'Oracle', 'Redis', 'RabbitMQ', 'Kafka',
                'MyBatis', 'ShardingSphere', 'Redisson', 'Druid', 'HikariCP',
                'FastJSON', 'Jackson', 'Gson', 'Hutool', 'Guava',
                'Django', 'Flask', 'FastAPI', 'React', 'Vue', 'Angular', 'Node.js'
            }

            # 拆分包含多个技术的项
            parts = []
            current_word = ''
            for char in cleaned + ' ':  # 添加空格确保最后一个词被处理
                if char == ' ':
                    if current_word:
                        # 检查是否是已知技术
                        if current_word in core_technologies or len(current_word) > 2:
                            parts.append(current_word)
                        current_word = ''
                else:
                    current_word += char

            # 如果拆分后只有一个词且长度较长，可能是合并的技术，尝试按大写字母拆分
            if len(parts) == 1 and len(parts[0]) > 20:
                # 尝试按大写字母拆分 "MySQLShardingSphere" -> ["MySQL", "ShardingSphere"]
                merged = parts[0]
                split_parts = []
                current = ''
                for char in merged:
                    if char.isupper() and current:
                        split_parts.append(current)
                        current = char
                    else:
                        current += char
                if current:
                    split_parts.append(current)
                if len(split_parts) > 1:
                    parts = split_parts

            return parts

        # 清理现有技术栈
        cleaned_tech_list = []
        for tech in result.get('tech_stack', []):
            cleaned_parts = clean_and_split_tech(tech)
            for part in cleaned_parts:
                # 过滤掉目录路径和章节标题
                if part and '/' not in part and not part.startswith('**') and not part.endswith('**'):
                    cleaned_tech_list.append(part)

        # 当前技术栈（转为小写用于比较）
        current_tech_lower = [t.lower() for t in cleaned_tech_list]

        # 从文档中查找额外的核心技术
        additional_tech = []
        for tech in core_tech:
            if tech.lower() in all_content and tech.lower() not in current_tech_lower:
                additional_tech.append(tech)

        # 从亮点中推断核心技术
        highlights = result.get('highlights', [])
        for highlight in highlights:
            for keyword, techs in highlight_tech_mapping.items():
                if keyword in highlight:
                    for tech in techs:
                        if tech.lower() in all_content and tech.lower() not in current_tech_lower and tech not in additional_tech:
                            additional_tech.append(tech)
                            break

        # 合并并去重
        final_tech = cleaned_tech_list + additional_tech

        # 去重并过滤
        seen = set()
        unique_tech = []
        filter_list = ['spring', 'git', 'maven', 'gradle', 'lombok', 'log4j', 'logback', 'slf4j',
                      'alipay', 'wechat pay', 'unionpay', 'mybatis spring boot starter', 'go']

        for tech in final_tech:
            tech_lower = tech.lower()
            if tech_lower in filter_list:
                continue
            if tech_lower not in seen and tech_lower:
                seen.add(tech_lower)
                unique_tech.append(tech)

        result['tech_stack'] = unique_tech

        if additional_tech:
            logger.info(f"补充技术栈: {additional_tech}")

        logger.info(f"_supplement_tech_stack 返回: description='{result.get('description', '')[:30]}...', highlights={len(result.get('highlights', []))} 条")

        return result

    def _fallback_analyze(self, documents: List[str]) -> Dict:
        """降级分析：基于规则提取"""
        result = {
            "description": "",
            "tech_stack": [],
            "highlights": []
        }

        all_content = "\n".join(documents.values())

        # 提取技术栈（常见的框架/语言）
        tech_keywords = {
            'Python', 'Java', 'Go', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Rust',
            'React', 'Vue', 'Angular', 'Node.js', 'Django', 'Flask', 'FastAPI',
            'Spring', 'SpringBoot', 'MyBatis', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis',
            'Docker', 'Kubernetes', 'Git', 'Linux', 'Nginx',
            'LangGraph', 'Gradio', 'GitPython', 'LLM', 'Ollama'
        }

        found_tech = set()
        for tech in tech_keywords:
            if tech.lower() in all_content.lower():
                found_tech.add(tech)
        result["tech_stack"] = list(found_tech)

        # 提取描述（第一段）
        for content in documents.values():
            first_para = content.split('\n\n')[0]
            if len(first_para) > 10 and len(first_para) < 200:
                result["description"] = first_para[:100]
                break

        # 提取亮点（包含"性能"、"优化"等的句子）
        for content in documents.values():
            sentences = content.split('。')
            for sentence in sentences:
                if any(kw in sentence for kw in ['性能', '优化', '提升', '节省', '实现', '完成']):
                    if len(sentence) < 50:
                        result["highlights"].append(sentence.strip())
            if len(result["highlights"]) >= 3:
                break

        return result
