"""
依赖自动检查与安装模块
======================
在应用启动时检查关键依赖，缺失时自动从镜像站安装。
所有下载内容放置在项目目录内，避免污染系统环境。
"""

import importlib
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录（backend/）
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 镜像源配置（优先使用国内镜像加速）
PIP_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.douban.com/simple",
]

# 需要检查的关键依赖（导入名 -> pip包名）
CRITICAL_DEPS = {
    "pdfplumber": "pdfplumber",
    "fitz": "PyMuPDF",
    "docx": "python-docx",
    "paddleocr": "paddleocr",
    "paddle": "paddlepaddle",
    "cv2": "opencv-python-headless",
    "PIL": "Pillow",
    "numpy": "numpy",
}

# 可选依赖（缺失不阻塞启动，使用时再检查）
OPTIONAL_DEPS = {
    "magic": "python-magic",
    "langdetect": "langdetect",
    "jieba": "jieba",
    "chardet": "chardet",
}


def _get_pip_path() -> str:
    """获取当前 Python 环境下的 pip 路径"""
    pip_path = os.path.join(os.path.dirname(sys.executable), "pip.exe")
    if os.path.exists(pip_path):
        return pip_path
    pip_path = os.path.join(os.path.dirname(sys.executable), "Scripts", "pip.exe")
    if os.path.exists(pip_path):
        return pip_path
    return "pip"


def _install_package(package_name: str, mirrors: list = None) -> bool:
    """
    使用镜像站安装单个包
    
    Args:
        package_name: pip 包名
        mirrors: 镜像源列表
    
    Returns:
        是否安装成功
    """
    if mirrors is None:
        mirrors = PIP_MIRRORS

    pip = _get_pip_path()
    
    for mirror in mirrors:
        try:
            cmd = [pip, "install", "--no-cache-dir", "-i", mirror, "--trusted-host", mirror.split("://")[1].split("/")[0], package_name]
            logger.info(f"正在从镜像站安装 {package_name}: {mirror}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info(f"安装成功: {package_name}")
                return True
            else:
                logger.warning(f"镜像 {mirror} 安装失败: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"镜像 {mirror} 安装超时: {package_name}")
        except Exception as e:
            logger.warning(f"镜像 {mirror} 安装异常: {str(e)}")
    
    # 回退到官方源
    try:
        logger.info(f"回退到官方源安装: {package_name}")
        cmd = [pip, "install", "--no-cache-dir", package_name]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            logger.info(f"官方源安装成功: {package_name}")
            return True
    except Exception:
        pass
    
    return False


def check_and_install_deps() -> dict:
    """
    检查并安装关键依赖
    
    Returns:
        {"installed": [...], "missing": [...], "failed": [...]}
    """
    result = {"installed": [], "missing": [], "failed": []}
    
    for import_name, package_name in CRITICAL_DEPS.items():
        try:
            importlib.import_module(import_name)
            result["installed"].append(package_name)
        except ImportError:
            result["missing"].append(package_name)
            logger.info(f"检测到缺失依赖: {package_name}，尝试自动安装...")
            if _install_package(package_name):
                result["installed"].append(package_name)
                result["missing"].remove(package_name)
            else:
                result["failed"].append(package_name)
                logger.warning(f"依赖安装失败: {package_name}，相关功能将不可用")
    
    if result["failed"]:
        logger.warning(f"以下依赖安装失败，相关功能将受限: {result['failed']}")
    
    if result["missing"]:
        logger.info(f"以下依赖未安装（非阻塞）: {result['missing']}")
    
    return result


def ensure_ocr_available() -> bool:
    """
    确保 OCR 依赖可用（使用时调用）
    如果未安装则自动安装
    """
    try:
        import paddleocr
        return True
    except ImportError:
        logger.warning("PaddleOCR 未安装，尝试自动安装...")
        if _install_package("paddleocr"):
            if _install_package("paddlepaddle"):
                logger.info("PaddleOCR 安装完成")
                return True
            else:
                logger.error("PaddlePaddle 安装失败，OCR 功能不可用")
                return False
        logger.error("PaddleOCR 安装失败")
        return False


def ensure_fitz_available() -> bool:
    """确保 PyMuPDF 可用"""
    try:
        import fitz
        return True
    except ImportError:
        logger.warning("PyMuPDF 未安装，尝试自动安装...")
        return _install_package("PyMuPDF")


def ensure_pdfplumber_available() -> bool:
    """确保 pdfplumber 可用"""
    try:
        import pdfplumber
        return True
    except ImportError:
        logger.warning("pdfplumber 未安装，尝试自动安装...")
        return _install_package("pdfplumber")