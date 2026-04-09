"""输出校验器"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class ValidationResult:
    """校验结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class OutputValidator:
    """输出校验器

    职责：
    1. 确保格式正确
    2. 确保不为空
    3. 确保符合 mode 要求
    """

    def __init__(self):
        # 简约模式规则
        self.simple_rules = {
            "min_length": 10,
            "max_length": 3000,
            "required_structure": False  # 简约模式不强求结构
        }
        # 专业模式规则
        self.professional_rules = {
            "min_length": 20,
            "max_length": 5000,
            "required_structure": True  # 专业模式需要有结构
        }

    def validate(self, content: str, mode: str) -> ValidationResult:
        """校验输出

        Args:
            content: 要校验的内容
            mode: 模式（simple/professional）

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # 1. 非空检查
        if not content or not content.strip():
            return ValidationResult(
                is_valid=False,
                errors=["输出为空"],
                warnings=warnings
            )

        # 2. 根据模式选择规则
        rules = self.professional_rules if mode == "professional" else self.simple_rules

        # 3. 长度检查
        content_len = len(content)
        if content_len < rules["min_length"]:
            errors.append(f"输出过短（{content_len} < {rules['min_length']}字符）")
        elif content_len > rules["max_length"]:
            warnings.append(f"输出过长（{content_len} > {rules['max_length']}字符）")

        # 4. 结构检查（专业模式）
        if rules["required_structure"]:
            if not self._has_structure(content):
                warnings.append("专业模式建议使用更清晰的结构（分段、列表等）")

        # 5. 格式检查
        format_issues = self._check_format(content)
        errors.extend(format_issues["errors"])
        warnings.extend(format_issues["warnings"])

        # 6. 内容质量检查
        quality_issues = self._check_quality(content)
        warnings.extend(quality_issues)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _has_structure(self, content: str) -> bool:
        """检查是否有结构（分段、列表等）"""
        # 有段落分隔
        if '\n\n' in content:
            return True
        # 有列表
        if any(marker in content for marker in ['1.', '2.', '3.', '-', '•', '*']):
            return True
        # 有标题
        if any(marker in content for marker in ['#', '##', '###', '一、', '二、']):
            return True
        return False

    def _check_format(self, content: str) -> dict:
        """检查格式问题"""
        errors = []
        warnings = []

        # 检查是否有未闭合的标记
        if '```' in content and content.count('```') % 2 != 0:
            errors.append("代码块标记未闭合")

        # 检查是否有过多空白行
        empty_line_count = content.count('\n\n')
        if empty_line_count > 10:
            warnings.append(f"空白行过多（{empty_line_count}处）")

        return {"errors": errors, "warnings": warnings}

    def _check_quality(self, content: str) -> List[str]:
        """检查内容质量"""
        warnings = []

        # 检查是否有占位符
        placeholders = ['[...]', '...', '（待补充）', 'TODO', 'xxx']
        for placeholder in placeholders:
            if placeholder in content:
                warnings.append(f"包含占位符: {placeholder}")
                break

        # 检查是否有过短段落
        paragraphs = content.split('\n\n')
        short_paragraphs = [p for p in paragraphs if len(p.strip()) < 10 and p.strip()]
        if len(short_paragraphs) > len(paragraphs) / 2:
            warnings.append("有过短的段落")

        return warnings
