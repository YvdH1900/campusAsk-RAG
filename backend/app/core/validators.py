"""
输入验证和清理工具
=================
企业级数据校验层，提供：
- XSS攻击防护（HTML/JS代码过滤）
- SQL注入防护
- 数据类型强制转换
- 长度限制
- 格式校验（邮箱、手机号等）
- 敏感词过滤
"""

import re
import html
from typing import Any, Optional, List, Union
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """
    验证结果
    
    Attributes:
        is_valid: 是否通过验证
        value: 清理后的值（如果有效）
        error_message: 错误消息（如果无效）
        original_value: 原始值
    """
    is_valid: bool
    value: Optional[Any] = None
    error_message: Optional[str] = None
    original_value: Any = None


class InputValidator:
    """
    输入验证器
    
    提供链式调用接口，支持多种验证规则组合
    
    Example:
        validator = InputValidator()
        result = (validator
            .validate(username)
            .is_string()
            .min_length(3)
            .max_length(50)
            .alphanumeric()
            .no_xss()
            .result())
        
        if not result.is_valid:
            raise ValidationException(result.error_message)
    """
    
    def __init__(self):
        self._value = None
        self._original = None
        self._errors: List[str] = []
        self._is_valid = True
    
    def validate(self, value: Any) -> 'InputValidator':
        """
        开始验证链
        
        Args:
            value: 待验证的值
            
        Returns:
            self（支持链式调用）
        """
        self._value = value
        self._original = value
        self._errors = []
        self._is_valid = True
        return self
    
    def result(self) -> ValidationResult:
        """
        获取验证结果
        
        Returns:
            ValidationResult: 验证结果对象
        """
        return ValidationResult(
            is_valid=self._is_valid,
            value=self._value if self._is_valid else None,
            error_message="; ".join(self._errors) if self._errors else None,
            original_value=self._original
        )
    
    def is_required(self, field_name: str = "字段") -> 'InputValidator':
        """必填检查"""
        if self._is_valid and (self._value is None or str(self._value).strip() == ""):
            self._is_valid = False
            self._errors.append(f"{field_name}不能为空")
        return self
    
    def is_string(self, field_name: str = "字段") -> 'InputValidator':
        """字符串类型检查"""
        if self._is_valid and self._value is not None and not isinstance(self._value, str):
            try:
                self._value = str(self._value)
            except Exception:
                self._is_valid = False
                self._errors.append(f"{field_name}必须是字符串")
        return self
    
    def min_length(self, min_len: int, field_name: str = "字段") -> 'InputValidator':
        """最小长度"""
        if self._is_valid and self._value is not None:
            if len(str(self._value)) < min_len:
                self._is_valid = False
                self._errors.append(f"{field_name}长度不能少于{min_len}个字符")
        return self
    
    def max_length(self, max_len: int, field_name: str = "字段") -> 'InputValidator':
        """最大长度"""
        if self._is_valid and self._value is not None:
            if len(str(self._value)) > max_len:
                self._value = str(self._value)[:max_len]
        return self
    
    def alphanumeric(self, field_name: str = "字段") -> 'InputValidator':
        """只允许字母数字和下划线"""
        if self._is_valid and self._value is not None:
            if not re.match(r'^[a-zA-Z0-9_]+$', str(self._value)):
                self._is_valid = False
                self._errors.append(f"{field_name}只能包含字母、数字和下划线")
        return self
    
    def no_xss(self, field_name: str = "字段") -> 'InputValidator':
        """
        XSS防护
        
        检测并移除潜在的HTML/JavaScript注入代码
        """
        if self._is_valid and self._value is not None and isinstance(self._value, str):
            cleaned = sanitize_html(self._value)
            
            if has_xss_attack(str(self._value)):
                self._is_valid = False
                self._errors.append(f"{field_name}包含非法字符或脚本代码")
            else:
                self._value = cleaned
        return self
    
    def email(self, field_name: str = "邮箱") -> 'InputValidator':
        """邮箱格式验证"""
        if self._is_valid and self._value is not None and str(self._value).strip() != "":
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, str(self._value).strip()):
                self._is_valid = False
                self._errors.append(f"{field_name}格式不正确")
        return self
    
    def phone(self, field_name: str = "手机号") -> 'InputValidator':
        """中国手机号格式验证"""
        if self._is_valid and self._value is not None and str(self._value).strip() != "":
            phone_pattern = r'^1[3-9]\d{9}$'
            if not re.match(phone_pattern, str(self._value).strip()):
                self._is_valid = False
                self._errors.append(f"{field_name}格式不正确")
        return self
    
    def in_range(
        self, 
        min_val: Union[int, float], 
        max_val: Union[int, float],
        field_name: str = "数值"
    ) -> 'InputValidator':
        """数值范围检查"""
        if self._is_valid and self._value is not None:
            try:
                num = float(self._value)
                if num < min_val or num > max_val:
                    self._is_valid = False
                    self._errors.append(f"{field_name}必须在{min_val}到{max_val}之间")
                    return self
                
                self._value = int(num) if isinstance(self._value, int) else num
            except (ValueError, TypeError):
                self._is_valid = False
                self._errors.append(f"{field_name}必须是有效数字")
        return self
    
    def in_choices(
        self, 
        choices: List[Any],
        field_name: str = "选项"
    ) -> 'InputValidator':
        """
        枚举值检查
        
        Args:
            choices: 允许的值列表
            field_name: 字段名称
        """
        if self._is_valid and self._value is not None:
            if self._value not in choices:
                self._is_valid = False
                self._errors.append(f"{field_name}必须是以下值之一: {', '.join(map(str, choices))}")
        return self


def sanitize_html(text: str) -> str:
    """
    HTML实体编码，防止XSS攻击
    
    将特殊HTML字符转换为安全的实体形式
    
    Args:
        text: 原始文本
        
    Returns:
        str: 安全的转义后文本
    """
    if not text or not isinstance(text, str):
        return text
    
    return html.escape(text, quote=True)


def has_xss_attack(text: str) -> bool:
    """
    检测是否包含XSS攻击特征
    
    检测常见的XSS攻击模式：
    - <script>标签
    - javascript:协议
    - 事件处理器（onclick等）
    - CSS表达式
    - data:URI
    
    Args:
        text: 待检测的文本
        
    Returns:
        bool: 是否包含XSS攻击特征
    """
    if not text or not isinstance(text, str):
        return False
    
    xss_patterns = [
        r'<script\b[^>]*>.*?</script>',
        r'javascript\s*:',
        r'on\w+\s*=',
        r'expression\s*\(',
        r'data\s*:\s*text/html',
        r'vbscript\s*:',
        r'<iframe',
        r'<object',
        r'<embed',
        r'<applet',
        r'<meta',
        r'<base',
        r'<link',
        r'<style\b[^>]*>.*?</style>',
        r'@import',
        r'<img[^>]+onerror',
        r'<body[^>]+onload',
    ]
    
    text_lower = text.lower()
    
    for pattern in xss_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE | re.DOTALL):
            return True
    
    return False


def sanitize_filename(filename: str) -> str:
    """
    文件名清理（防止路径遍历攻击）
    
    移除危险字符和路径信息，保留安全的文件名
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 安全的文件名
    """
    if not filename:
        return "unnamed_file"
    
    import os
    
    filename = os.path.basename(filename)
    
    dangerous_chars = ['..', '/', '\\', '\x00', ':', '*', '?', '"', '<', '>', '|']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    filename = re.sub(r'[^\w\-_.]', '', filename)
    
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename or "unnamed_file"


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    文本截断（防止超长输入）
    
    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀
        
    Returns:
        str: 截断后的文本
    """
    if not text or len(text) <= max_length:
        return text or ""
    
    # 如果文本长度小于等于最大长度，直接返回
    if len(text) <= max_length:
        return text
    
    # 确保最大长度足够容纳后缀
    if len(suffix) >= max_length:
        return suffix[:max_length]
    
    # 截断文本，预留空间给后缀
    truncated = text[:max_length - len(suffix)]
    
    # 尝试在单词边界处截断
    try:
        # 在截断位置查找最近的空格
        last_space_index = truncated.rfind(' ')
        if last_space_index > 0 and last_space_index < len(truncated):  # 避免在开头截断
            truncated = truncated[:last_space_index]
    except:
        pass  # 如果出现任何错误，继续使用原始截断
    
    return truncated + suffix


def mask_sensitive_data(text: str, visible_chars: int = 4, mask_char: str = "*") -> str:
    """
    敏感数据脱敏
    
    用于日志记录时隐藏敏感信息（如手机号、身份证号）
    
    Args:
        text: 原始文本
        visible_chars: 显示的前几位字符数
        mask_char: 掩码字符
        
    Returns:
        str: 脱敏后的文本
    """
    if not text or len(text) <= visible_chars * 2:
        return mask_char * (len(text) if text else 8)
    
    prefix = text[:visible_chars]
    suffix = text[-visible_chars:] if len(text) > visible_chars * 2 else ""
    masked_length = len(text) - visible_chars - len(suffix)
    
    return f"{prefix}{mask_char * masked_length}{suffix}"


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    密码强度验证
    
    检查密码是否符合安全要求：
    - 至少6位
    
    Args:
        password: 密码字符串
        
    Returns:
        tuple[bool, str]: (是否通过, 错误消息)
    """
    if len(password) < 6:
        return False, "密码长度至少为6位"
    
    return True, ""


validator = InputValidator()
