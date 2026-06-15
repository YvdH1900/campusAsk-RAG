"""
生成层真实环境测试
=================
通过 HTTP API 测试答案生成质量：扎根度、关键词命中率、内容片段覆盖率、
响应延迟、拒答处理、边界条件、多轮对话、流式输出。

前置条件：
- uvicorn 服务运行中 (localhost:8000)
- MySQL + Milvus 可用
- 有 completed 文档
"""
import json
import time
import urllib.request
import urllib.error
import pytest
import jieba


# ============================================================
# 测试数据
# ============================================================

def _load_golden_dataset():
    """从 golden_dataset 加载测试问题"""
    from tests.evaluation.golden_dataset import GOLDEN_DATASET, get_questions_by_difficulty

    _easy_qs = get_questions_by_difficulty("easy")[:4]
    _medium_qs = get_questions_by_difficulty("medium")[:4]
    _hard_qs = get_questions_by_difficulty("hard")[:4]
    return [(qa.question, qa.expected_keywords, qa.expected_content)
            for qa in _easy_qs + _medium_qs + _hard_qs]


TEST_QUESTIONS = _load_golden_dataset()

REJECTION_TEST_QUESTIONS = [
    "清华大学校长是谁？",
    "火星殖民地如何申请？",
]

STOPWORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "为什么",
    "可以", "能", "吗", "呢", "吧", "啊", "呀", "哦", "嗯", "而", "但", "但是", "如果",
    "因为", "所以", "虽然", "然后", "之后", "以后", "之前", "以前", "现在", "已经", "正在",
    "学校", "学生", "根据", "相关", "规定", "要求", "需要", "应该", "必须", "对于", "关于",
])

REJECTION_PHRASES = [
    "无法找到", "未找到", "没有找到", "抱歉", "不清楚",
    "暂无相关", "知识库中", "无法回答", "暂时无法", "没有相关",
    "无法从", "未能在", "未检索到",
]


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="session")
def auth_token():
    """获取 JWT token"""
    try:
        d = json.dumps({"username": "admin", "password": "123456"}).encode()
        req = urllib.request.Request("http://localhost:8000/api/v1/auth/login", data=d, headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read().decode())
        token = resp.get("access_token", "")
        if not token:
            pytest.skip("无法获取 auth token")
        return token
    except Exception as e:
        pytest.skip(f"后端不可用，跳过生成层测试: {e}")


def _api_call(url, payload, token, timeout=30):
    """通用 API 调用"""
    d = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=d, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    })
    try:
        resp_obj = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp_obj.read().decode()), resp_obj.status
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return body, e.code


# ============================================================
# L1: 系统健康检查
# ============================================================

@pytest.mark.generation
class TestSystemHealth:
    """L1: 系统健康检查"""

    def test_database_health(self):
        """验证数据库连接及已完成处理的文档数量"""
        from app.core.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            rows = db.execute(text("SELECT count(*) FROM documents WHERE status='completed'")).fetchall()
            count = rows[0][0]
            assert count > 0, "No completed documents found"
            print(f"\n{count} completed documents")
        finally:
            db.close()


# ============================================================
# L2: 检索测试
# ============================================================

@pytest.mark.generation
class TestRetrieval:
    """L2: 检索测试"""

    def test_eval_retrieve_returns_results(self, auth_token):
        """验证 eval-retrieve 接口对测试问题返回检索结果（至少 50%）"""
        count = 0
        for q, kw, ec in TEST_QUESTIONS:
            try:
                resp, status = _api_call("http://localhost:8000/api/v1/chat/eval-retrieve", {"content": q}, auth_token, timeout=30)
                if status == 200 and len(resp.get("results", [])) > 0:
                    count += 1
            except Exception:
                pass

        total = len(TEST_QUESTIONS)
        assert count > 0, f"All {total} queries returned 0 results"
        assert count >= total * 0.5, f"{count}/{total} queries returned results (need >= 50%)"
        print(f"\n{count}/{total} queries returned results")


# ============================================================
# L3: 生成质量测试
# ============================================================

@pytest.mark.generation
class TestAnswerGeneration:
    """L3: 生成质量测试"""

    @pytest.mark.parametrize("question,expected_keywords,expected_content", TEST_QUESTIONS)
    def test_answer_quality(self, question, expected_keywords, expected_content, auth_token):
        """对每个测试问题评估：扎根度、关键词命中率、内容片段覆盖率、延迟、来源引用"""
        t0 = time.time()

        resp, status = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": question}, auth_token, timeout=60)
        assert status == 200, f"HTTP {status}"

        ans = resp.get("answer", "")
        sources = resp.get("sources", [])
        cc = resp.get("context_count", 0)

        resp2, _ = _api_call("http://localhost:8000/api/v1/chat/eval-retrieve", {"content": question}, auth_token, timeout=30)
        ctx_list = resp2.get("results", [])
        ctx_text = " ".join(c.get("content", "") for c in ctx_list)

        # 扎根度
        ans_tokens = set(jieba.cut(ans)) - STOPWORDS if ans else set()
        ctx_tokens = set(jieba.cut(ctx_text)) - STOPWORDS if ctx_text else set()
        overlap = ans_tokens & ctx_tokens if ctx_tokens else set()
        grounded = len(overlap) / len(ans_tokens) if len(ans_tokens) > 0 else 0.0

        # 关键词命中率
        kw_matched = 0
        for k in expected_keywords:
            if k in ans:
                kw_matched += 1
            elif len(k) >= 4:
                for i in range(len(k) - 2):
                    if k[i:i+3] in ans:
                        kw_matched += 1
                        break
        kw_ratio = kw_matched / len(expected_keywords) if expected_keywords else 0.0

        # 内容片段命中率
        content_matched = 0
        content_total = len(expected_content) if expected_content else 0
        if expected_content:
            for ec in expected_content:
                core_phrases = []
                if len(ec) >= 4:
                    for i in range(0, len(ec) - 3, 2):
                        phrase = ec[i:i + 4]
                        if not all(c in "的了在是和就不人都一个上也很到说要去你会着没有看好自己这" for c in phrase):
                            core_phrases.append(phrase)
                if len(ec) < 4 and len(ec) >= 2:
                    core_phrases.append(ec)
                if any(phrase in ans for phrase in core_phrases):
                    content_matched += 1
        content_ratio = content_matched / content_total if content_total > 0 else 0.0

        latency = time.time() - t0
        source_present = len(sources) > 0 if cc > 0 else True

        # 判定
        pass_grounded = grounded >= 0.50
        pass_kw = kw_ratio >= 0.25
        pass_content = content_ratio >= 0.20 or content_total == 0
        pass_latency = latency <= 30.0
        pass_source = source_present

        assert bool(ans), "答案为空"
        assert pass_grounded, f"扎根度过低: {grounded:.3f}"
        assert pass_kw, f"关键词命中率过低: {kw_ratio:.3f} ({kw_matched}/{len(expected_keywords)})"
        assert pass_content, f"内容覆盖率过低: {content_ratio:.3f} ({content_matched}/{content_total})"
        assert pass_latency, f"响应过慢: {latency:.1f}s"
        assert pass_source, "sources 字段为空"

        print(f"\n[{question[:25]}] g={grounded:.3f} kw={kw_matched}/{len(expected_keywords)} ct={content_matched}/{content_total} lat={latency:.1f}s")


# ============================================================
# L4: 拒答测试
# ============================================================

@pytest.mark.generation
class TestRejection:
    """L4: 拒答测试"""

    @pytest.mark.parametrize("question", REJECTION_TEST_QUESTIONS)
    def test_rejection(self, question, auth_token):
        """验证知识库无结果时系统不会编造答案"""
        resp, status = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": question}, auth_token, timeout=60)
        assert status == 200, f"HTTP {status}"

        ans = resp.get("answer", "")
        cc = resp.get("context_count", 0)

        has_rejection_phrase = any(phrase in ans for phrase in REJECTION_PHRASES)
        no_context_short = cc == 0 and len(ans) < 50
        correctly_rejected = has_rejection_phrase or no_context_short

        assert correctly_rejected, f"系统编造了答案: {ans[:100]}"
        print(f"\n[{question}] correctly rejected")


# ============================================================
# L5: 边界条件测试
# ============================================================

@pytest.mark.generation
class TestEdgeCases:
    """L5: 边界条件测试"""

    @pytest.mark.parametrize("name,content,should_fail", [
        ("空输入", "", True),
        ("纯空格", "   ", True),
        ("超长输入", "A" * 5000, False),
        ("HTML注入", "<script>alert('xss')</script>", False),
        ("SQL注入", "'; DROP TABLE users; --", False),
    ])
    def test_edge_case(self, name, content, should_fail, auth_token):
        """验证系统对异常输入的处理"""
        resp, status_code = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": content}, auth_token, timeout=60)
        ans = resp.get("answer", "")

        if should_fail:
            passed = status_code == 400 or ans == ""
        else:
            passed = (status_code == 200 and ans != "") or status_code == 400

        assert passed, f"{name}: status={status_code}, ans_len={len(ans)}"
        print(f"\n[{name}] status={status_code}, passed={passed}")


# ============================================================
# L6: 多轮对话测试
# ============================================================

@pytest.mark.generation
class TestMultiTurn:
    """L6: 多轮对话测试"""

    @pytest.mark.parametrize("questions,expected_kw", [
        (["上海交通大学的校训是什么？", "它体现了什么精神？"], ["饮水思源", "爱国荣校"]),
        (["交大学生如何申请休学？", "那复学需要什么条件？"], ["复学", "申请"]),
        (["GPA低于1.7会怎样？", "第二次低于1.7呢？"], ["退学警告", "试读"]),
    ])
    def test_multi_turn_context(self, questions, expected_kw, auth_token):
        """验证上下文关联能力（代词指代、省略主语、递进追问）"""
        resp1, status1 = _api_call("http://localhost:8000/api/v1/chat/ask",
                                   {"content": questions[0]}, auth_token, timeout=60)
        assert status1 == 200, f"第一轮HTTP {status1}"

        session_id = resp1.get("session_id")
        assert session_id, "未返回session_id"

        resp2, status2 = _api_call("http://localhost:8000/api/v1/chat/ask",
                                   {"content": questions[1], "session_id": session_id},
                                   auth_token, timeout=60)
        assert status2 == 200, f"第二轮HTTP {status2}"

        ans2 = resp2.get("answer", "")
        kw_matched = sum(1 for k in expected_kw if k in ans2)
        kw_ratio = kw_matched / len(expected_kw) if expected_kw else 0.0

        assert kw_ratio >= 0.30, f"关键词命中率过低: {kw_ratio:.2f} ({kw_matched}/{len(expected_kw)})"
        assert bool(ans2), "第二轮答案为空"
        print(f"\n[{questions[1][:25]}] kw={kw_matched}/{len(expected_kw)}")


# ============================================================
# L7: 流式输出测试
# ============================================================

@pytest.mark.generation
class TestStreaming:
    """L7: 流式输出测试"""

    def test_streaming_output(self, auth_token):
        """验证 /ask/stream 完整性"""
        test_q = "上海交通大学的校训是什么？"

        t0 = time.time()
        d = json.dumps({"content": test_q}).encode()
        req = urllib.request.Request("http://localhost:8000/api/v1/chat/ask/stream",
                                     data=d, headers={
                                         "Authorization": "Bearer " + auth_token,
                                         "Content-Type": "application/json",
                                     })
        resp_obj = urllib.request.urlopen(req, timeout=60)

        chunks = []
        done_data = None
        first_chunk_time = None

        for line in resp_obj:
            line = line.decode('utf-8').strip()
            if line.startswith('data: '):
                data_str = line[6:]
                if data_str == '[DONE]':
                    break
                try:
                    event = json.loads(data_str)
                    if event.get('type') == 'chunk':
                        if first_chunk_time is None:
                            first_chunk_time = time.time() - t0
                        chunks.append(event.get('content', ''))
                    elif event.get('type') == 'done':
                        done_data = event
                except json.JSONDecodeError:
                    pass

        total_latency = time.time() - t0

        has_chunks = len(chunks) > 0
        has_done = done_data is not None
        stream_answer = ''.join(chunks)
        done_answer = done_data.get('answer', '') if done_data else ''
        answer_match = stream_answer == done_answer
        first_byte_ok = first_chunk_time is not None and first_chunk_time < 10.0

        assert has_chunks, "没有收到 chunk"
        assert has_done, "没有收到 done 事件"
        assert answer_match, f"chunk 拼接与 done 答案不一致: stream={len(stream_answer)} done={len(done_answer)}"
        assert first_byte_ok, f"首字节时间过长: {first_chunk_time:.2f}s"

        print(f"\nstreaming: chunks={len(chunks)}, first_byte={first_chunk_time:.2f}s, total={total_latency:.2f}s")
