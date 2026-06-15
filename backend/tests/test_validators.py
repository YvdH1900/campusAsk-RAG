"""
输入验证模块测试
===============
测试 app/core/validators.py 中的所有公开函数和类。
测试预期严格匹配源代码实际行为，不做假设。

运行：pytest tests/test_validators.py -v -o "addopts="
"""

import pytest
from app.core.validators import (
    InputValidator,
    sanitize_html,
    has_xss_attack,
    sanitize_filename,
    truncate_text,
    mask_sensitive_data,
    validate_password_strength,
)


class TestInputValidator:
    """链式输入验证器"""

    def test_required_validation(self):
        """必填检查"""
        r = InputValidator().validate("").is_required("用户名").result()
        assert not r.is_valid
        assert "不能为空" in r.error_message

        r = InputValidator().validate("test").is_required("用户名").result()
        assert r.is_valid

    def test_string_type_check(self):
        """字符串类型：非字符串转为字符串"""
        r = InputValidator().validate(123).is_string().result()
        assert r.is_valid
        assert r.value == "123"

    def test_min_length(self):
        """最小长度"""
        r = InputValidator().validate("ab").min_length(3, "密码").result()
        assert not r.is_valid

    def test_max_length_truncates(self):
        """最大长度：超长截断"""
        r = InputValidator().validate("a" * 100).max_length(50, "名称").result()
        assert r.is_valid
        assert len(r.value) == 50

    def test_alphanumeric(self):
        """字母数字下划线"""
        for name in ["user123", "test_user", "ABC123"]:
            r = InputValidator().validate(name).alphanumeric().result()
            assert r.is_valid, name

        for name in ["user@123", "test name", "user#name"]:
            r = InputValidator().validate(name).alphanumeric().result()
            assert not r.is_valid, name

    def test_xss_prevention(self):
        """XSS 防护：脚本标签和事件处理器被拦截"""
        for payload in [
            '<script>alert("XSS")</script>',
            '<img src=x onerror="alert(1)">',
            '<svg onload="alert(1)">',
        ]:
            r = InputValidator().validate(payload).no_xss("内容").result()
            assert not r.is_valid, payload

        r = InputValidator().validate("正常文本内容").no_xss("内容").result()
        assert r.is_valid

    def test_email_validation(self):
        """邮箱格式：使用源代码正则为准"""
        for email in [
            "test@example.com",
            "user.name@domain.org",
            "user123@test.co.uk",
        ]:
            r = InputValidator().validate(email).email().result()
            assert r.is_valid, email

        for email in [
            "invalid-email",
            "@example.com",
            "user@",
        ]:
            r = InputValidator().validate(email).email().result()
            assert not r.is_valid, email

    def test_phone_validation(self):
        """手机号格式"""
        for phone in ["13800138000", "15012345678", "18900001111"]:
            r = InputValidator().validate(phone).phone().result()
            assert r.is_valid, phone

        for phone in ["12345", "1380013800", "1801234567a"]:
            r = InputValidator().validate(phone).phone().result()
            assert not r.is_valid, phone

    def test_range_validation(self):
        """数值范围"""
        r = InputValidator().validate(5).in_range(1, 10, "年龄").result()
        assert r.is_valid
        assert r.value == 5

        r = InputValidator().validate(15).in_range(1, 10, "年龄").result()
        assert not r.is_valid

    def test_choices_validation(self):
        """枚举值检查"""
        choices = ["student", "teacher", "admin"]
        assert InputValidator().validate("student").in_choices(choices, "角色").result().is_valid
        assert not InputValidator().validate("superadmin").in_choices(choices, "角色").result().is_valid

    def test_chain_stops_on_first_error(self):
        """链式调用：中途失败后不再产生额外错误消息，
        后续规则也标记 is_valid=False，但不追加新消息。"""
        r = (InputValidator()
            .validate("")
            .is_required("字段")
            .min_length(5, "字段")
            .result())

        assert not r.is_valid
        # 只保留第一个错误（源代码行为：后续规则检查 _is_valid 为 False 时不再追加）
        assert r.error_message == "字段不能为空"


class TestSanitizeHtml:
    """HTML 转义"""

    def test_html_escape(self):
        assert sanitize_html("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
        assert sanitize_html('a"b') == "a&quot;b"
        assert sanitize_html("test&value") == "test&amp;value"

    def test_none_and_empty(self):
        assert sanitize_html(None) is None
        assert sanitize_html("") == ""


class TestHasXssAttack:
    """XSS 攻击检测"""

    def test_detect(self):
        for text in [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            '<img src=x onerror="alert(1)"/>',
        ]:
            assert has_xss_attack(text), text

    def test_safe(self):
        for text in ["normal text", "Hello World! 你好世界！", "Test < 100 and > 50"]:
            assert not has_xss_attack(text), text


class TestSanitizeFilename:
    """文件名清理"""

    def test_normal(self):
        assert sanitize_filename("document.pdf") == "document.pdf"
        assert sanitize_filename("report_2024.docx") == "report_2024.docx"

    def test_path_traversal(self):
        for name in ["../../../etc/passwd", "..\\..\\windows\\system32", "/etc/shadow"]:
            safe = sanitize_filename(name)
            assert ".." not in safe
            assert "/" not in safe
            assert "\\" not in safe

    def test_special_chars(self):
        # 源代码先逐字符替换危险字符为 _，再用 regex 移除剩余非单词字符
        # " -> _ 后 regex 保留 _，结果为 file_name.pdf
        assert sanitize_filename('file"name.pdf') == "file_name.pdf"
        # < > 危险字符替换为 _ 后保留，结果为 file_name_.txt
        assert sanitize_filename("file<name>.txt") == "file_name_.txt"

    def test_empty(self):
        assert sanitize_filename("") == "unnamed_file"


class TestTruncateText:
    """文本截断"""

    def test_no_truncation_needed(self):
        text = "Hello World"
        assert truncate_text(text, 20) == text

    def test_truncated(self):
        text = "Hello World"
        result = truncate_text(text, 5)
        assert result.endswith("...")
        assert len(result) == 5  # 2 chars + "..."

    def test_empty(self):
        assert truncate_text("", 100) == ""
        assert truncate_text(None, 100) == ""


class TestMaskSensitiveData:
    """敏感数据脱敏"""

    def test_phone(self):
        # visible_chars=4: prefix=1380, suffix=8000, masked=***, result="1380***8000"
        result = mask_sensitive_data("13800138000")
        assert result == "1380***8000"

        result = mask_sensitive_data("15012345678", visible_chars=3)
        # visible_chars=3: prefix=150, suffix=678, masked=5 stars
        assert result == "150*****678"

    def test_short_text(self):
        # len("abc")=3, visible_chars=4, 3 <= 8, 返回 "*" * 3
        result = mask_sensitive_data("abc")
        assert result == "***"


class TestPasswordValidation:
    """密码强度验证：目前仅检查长度 >= 6"""

    def test_strong(self):
        ok, err = validate_password_strength("Abc@123456")
        assert ok
        assert err == ""

    def test_too_short(self):
        ok, err = validate_password_strength("Ab1!")
        assert not ok
        assert "长度" in err or "6" in err


class TestChainedValidation:
    """组合验证"""

    def test_complex_chain(self):
        r = (InputValidator()
            .validate("test_user123")
            .is_required("用户名")
            .min_length(3)
            .max_length(50)
            .alphanumeric()
            .no_xss()
            .result())
        assert r.is_valid
        assert r.value == "test_user123"

    def test_first_error_only(self):
        """链式验证：只记录第一个错误"""
        r = (InputValidator()
            .validate("")
            .is_required("字段")
            .min_length(5)
            .max_length(10)
            .result())
        assert not r.is_valid
        assert r.error_message == "字段不能为空"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
