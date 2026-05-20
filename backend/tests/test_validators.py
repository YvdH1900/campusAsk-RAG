"""
单元测试：输入验证模块
=====================
测试所有输入验证和安全防护功能
"""

import pytest
from app.core.validators import (
    InputValidator,
    sanitize_html,
    has_xss_attack,
    sanitize_filename,
    truncate_text,
    mask_sensitive_data,
    validate_password_strength
)


class TestInputValidator:
    """输入验证器测试"""
    
    def test_required_validation(self):
        """测试必填检查"""
        result = InputValidator().validate("").is_required("用户名").result()
        assert not result.is_valid
        assert "不能为空" in result.error_message
        
        result = InputValidator().validate("test").is_required("用户名").result()
        assert result.is_valid
    
    def test_string_type_check(self):
        """测试字符串类型检查"""
        result = InputValidator().validate(123).is_string().result()
        assert result.is_valid
        assert result.value == "123"
    
    def test_length_validation(self):
        """测试长度限制"""
        result = (InputValidator()
            .validate("ab")
            .min_length(3, "密码")
            .result())
        assert not result.is_valid
        
        result = (InputValidator()
            .validate("a" * 100)
            .max_length(50, "名称")
            .result())
        assert result.is_valid
        assert len(result.value) <= 50
    
    def test_alphanumeric_validation(self):
        """测试字母数字检查"""
        valid_names = ["user123", "test_user", "ABC123"]
        invalid_names = ["user@123", "test name", "user#name"]
        
        for name in valid_names:
            result = InputValidator().validate(name).alphanumeric().result()
            assert result.is_valid, f"{name} 应该通过验证"
        
        for name in invalid_names:
            result = InputValidator().validate(name).alphanumeric().result()
            assert not result.is_valid, f"{name} 不应该通过验证"
    
    def test_xss_prevention(self):
        """测试XSS防护"""
        xss_payloads = [
            '<script>alert("XSS")</script>',
            'javascript:alert(1)',
            '<img src=x onerror="alert(1)">',
            '<svg onload="alert(1)">',
        ]
        
        for payload in xss_payloads:
            result = InputValidator().validate(payload).no_xss("内容").result()
            assert not result.is_valid, f"应该检测到XSS: {payload}"
        
        safe_content = "这是一段正常的文本内容"
        result = InputValidator().validate(safe_content).no_xss("内容").result()
        assert result.is_valid
    
    def test_email_validation(self):
        """测试邮箱格式验证"""
        valid_emails = [
            "test@example.com",
            "user.name@domain.org",
            "user123@test.co.uk",
        ]
        invalid_emails = [
            "invalid-email",
            "@example.com",
            "user@",
            "user..name@example.com",
        ]
        
        for email in valid_emails:
            result = InputValidator().validate(email).email().result()
            assert result.is_valid, f"{email} 应该是有效邮箱"
        
        for email in invalid_emails:
            result = InputValidator().validate(email).email().result()
            if email.strip():
                assert not result.is_valid, f"{email} 应该是无效邮箱"
    
    def test_phone_validation(self):
        """测试手机号格式验证"""
        valid_phones = ["13800138000", "15012345678", "18900001111"]
        invalid_phones = ["12345", "1380013800", "1801234567a", ""]
        
        for phone in valid_phones:
            result = InputValidator().validate(phone).phone().result()
            assert result.is_valid, f"{phone} 应该是有效手机号"
        
        for phone in invalid_phones:
            result = InputValidator().validate(phone).phone().result()
            if phone:
                assert not result.is_valid, f"{phone} 应该是无效手机号"
    
    def test_range_validation(self):
        """测试数值范围检查"""
        result = InputValidator().validate(5).in_range(1, 10, "年龄").result()
        assert result.is_valid
        assert result.value == 5
        
        result = InputValidator().validate(15).in_range(1, 10, "年龄").result()
        assert not result.is_valid
    
    def test_choices_validation(self):
        """测试枚举值检查"""
        choices = ["student", "teacher", "admin"]
        
        result = InputValidator().validate("student").in_choices(choices, "角色").result()
        assert result.is_valid
        
        result = InputValidator().validate("superadmin").in_choices(choices, "角色").result()
        assert not result.is_valid


class TestSanitizationFunctions:
    """清理函数测试"""
    
    def test_sanitize_html_basic(self):
        """基本HTML转义"""
        assert sanitize_html("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
        assert sanitize_html('a"b') == 'a&quot;b'
        assert sanitize_html("test&value") == "test&amp;value"
    
    def test_sanitize_html_none(self):
        """None值处理"""
        assert sanitize_html(None) is None
        assert sanitize_html("") == ""
    
    def test_has_xss_attack_detection(self):
        """XSS攻击检测"""
        attack_patterns = [
            ("<script>alert('xss')</script>", True),
            ("javascript:alert(1)", True),
            ('<img src=x onerror="alert(1)"/>', True),
            ("normal text", False),
            ("Hello World! 你好世界！", False),
            ("Test < 100 and > 50", False),
        ]
        
        for text, expected in attack_patterns:
            assert has_xss_attack(text) == expected, f"检测错误: {text}"
    
    def test_sanitize_filename_normal(self):
        """正常文件名处理"""
        assert sanitize_filename("document.pdf") == "document.pdf"
        assert sanitize_filename("report_2024.docx") == "report_2024.docx"
    
    def test_sanitize_filename_path_traversal(self):
        """路径遍历攻击防护"""
        dangerous_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/etc/shadow",
            "file\x00name",
        ]
        
        for filename in dangerous_filenames:
            safe_name = sanitize_filename(filename)
            assert ".." not in safe_name
            assert "/" not in safe_name
            assert "\\" not in safe_name
    
    def test_sanitize_filename_special_chars(self):
        """特殊字符处理"""
        assert sanitize_filename('file"name.pdf') == "file_name.pdf"
        assert sanitize_filename("file<name>.txt") == "filename_.txt"
    
    def test_truncate_text_normal(self):
        """正常文本截断"""
        text = "Hello World"
        assert truncate_text(text, 20) == text
        assert truncate_text(text, 5) == "Hello..."
    
    def test_truncate_text_empty(self):
        """空文本处理"""
        assert truncate_text("", 100) == ""
        assert truncate_text(None, 100) == ""
    
    def test_mask_sensitive_data_phone(self):
        """手机号脱敏"""
        assert mask_sensitive_data("13800138000") == "138****8000"
        assert mask_sensitive_data("15012345678", visible_chars=3) == "150****678"
    
    def test_mask_sensitive_data_short(self):
        """短文本脱敏"""
        result = mask_sensitive_data("abc")
        assert "*" in result
        assert len(result) >= 8


class TestPasswordValidation:
    """密码强度验证测试"""
    
    def test_strong_password(self):
        """强密码"""
        is_valid, error = validate_password_strength("Abc@123456")
        assert is_valid
        assert error == ""
    
    def test_weak_password_too_short(self):
        """太短的密码"""
        is_valid, error = validate_password_strength("Ab1!")
        assert not is_valid
        assert "长度" in error
    
    def test_password_no_lowercase(self):
        """缺少小写字母"""
        is_valid, error = validate_password_strength("ABCDEF123!")
        assert not is_valid
        assert "小写" in error
    
    def test_password_no_uppercase(self):
        """缺少大写字母"""
        is_valid, error = validate_password_strength("abcdef123!")
        assert not is_valid
        assert "大写" in error
    
    def test_password_no_digit(self):
        """缺少数字"""
        is_valid, error = validate_password_strength("Abcdefgh!")
        assert not is_valid
        assert "数字" in error
    
    def test_password_no_special_char(self):
        """缺少特殊字符"""
        is_valid, error = validate_password_strength("Abcdef1234")
        assert not is_valid
        assert "特殊字符" in error


class TestChainedValidation:
    """链式调用测试"""
    
    def test_complex_validation_chain(self):
        """复杂验证链"""
        username = "test_user123"
        result = (InputValidator()
            .validate(username)
            .is_required("用户名")
            .min_length(3)
            .max_length(50)
            .alphanumeric()
            .no_xss()
            .result())
        
        assert result.is_valid
        assert result.value == username
    
    def test_multiple_errors(self):
        """多个错误累积"""
        result = (InputValidator()
            .validate("")
            .is_required("字段")
            .min_length(5)
            .max_length(10)
            .result())
        
        assert not result.is_valid
        assert len(result.error_message.split(";")) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
