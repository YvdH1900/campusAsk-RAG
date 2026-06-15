
"""
评测测试的 Pytest Fixture
=================================
提供 RetrievalEvaluator 实例和 Golden Dataset 的 fixture。
"""

import pytest
from .retrieval_evaluator import RetrievalEvaluator
from .golden_dataset import GOLDEN_DATASET


@pytest.fixture(scope="session")
def golden_dataset():
    """金标准数据集"""
    return GOLDEN_DATASET


@pytest.fixture(scope="function")
def mock_evaluator():
    """使用 MOCK 模式的评测器（不依赖外部服务，可离线运行）"""
    return RetrievalEvaluator(top_k=5, use_mock=True)


@pytest.fixture(scope="function")
def real_evaluator():
    """使用 REAL 模式的评测器（需要真实 Milvus + Embedding API）"""
    return RetrievalEvaluator(top_k=5, use_mock=False)
