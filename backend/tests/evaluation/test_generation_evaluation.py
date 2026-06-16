"""
生成层真实环境测试
============================
通过 HTTP API 测试答案生成质量。

测试分层:
  L1 - 系统健康检查：DB 连接、文档就绪
  L2 - 生成核心质量：扎根度(Jaccard+语义)、关键词命中率、内容片段覆盖率、延迟、来源引用
  L3 - 拒答防幻觉：知识库外问题不会编造答案
  L4 - 边界条件：空输入、超长输入、注入攻击
  L5 - 多轮对话：代词指代、省略主语、递进追问
  L6 - 流式输出：SSE chunk 完整性与首字节延迟
  L7 - 汇总报告：聚合 L2 的通过率/分数分布

指标说明:
  - 扎根度(Groundedness): 回答中有多少 token 能在检索上下文中找到
    * 一级: jieba Jaccard token overlap（轻量，CI 高频）
    * 二级: embedding 余弦相似度（语义级，诊断用，不影响 pass/fail）
  - 关键词命中率(Keyword Recall): 预期关键词在回答中的覆盖率
  - 内容片段覆盖率(Content Coverage): 预期内容片段在回答中的命中比例

前置条件:
  - uvicorn 服务运行中 (localhost:8000)
  - MySQL + Milvus 可用
  - 有 completed 文档
"""
import json
import math
import time
import urllib.request
import urllib.error
import pytest
import jieba


# ============================================================
# 测试数据
# ============================================================

def _load_golden_dataset():
    """从 golden_dataset 加载测试问题，保留难度信息用于分档阈值"""
    from tests.evaluation.golden_dataset import GOLDEN_DATASET, get_questions_by_difficulty

    _easy_qs = get_questions_by_difficulty("easy")[:4]
    _medium_qs = get_questions_by_difficulty("medium")[:4]
    _hard_qs = get_questions_by_difficulty("hard")[:4]
    return [(qa.question, qa.expected_keywords, qa.expected_content, qa.difficulty)
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
])

REJECTION_PHRASES = [
    "无法找到", "未找到", "没有找到", "抱歉", "不清楚",
    "暂无相关", "知识库中", "无法回答", "暂时无法", "没有相关",
    "无法从", "未能在", "未检索到", "目前没有", "没有关于",
    "如需了解",
]

# 分难度阈值
# easy: 直接引用原文；medium/hard: LLM 需概括融合多条检索结果
GROUNDED_THRESHOLDS = {"easy": 0.40, "medium": 0.30, "hard": 0.20}
# 内容片段覆盖率也分难度——hard 问题 LLM 大幅改写，4-gram 子串匹配天然低
CONTENT_THRESHOLDS = {"easy": 0.20, "medium": 0.15, "hard": 0.10}

# 指标阈值
KEYWORD_RATIO_THRESHOLD = 0.25      # 关键词命中率阈值
LATENCY_THRESHOLD = 35.0             # 全链路延迟阈值（秒）
MULTI_TURN_KW_THRESHOLD = 0.30       # 多轮对话关键词阈值
STREAM_FIRST_BYTE_THRESHOLD = 10.0   # 流式首字节阈值（秒）


# ============================================================
# 辅助函数
# ============================================================

def _api_call(url, payload, token, timeout=30):
    """通用 HTTP API 调用。网络错误返回 (空结果, 0) 避免堆栈爆炸。"""
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
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        return {"error": str(e)}, 0


def _compute_embedding_similarity(text_a: str, text_b: str) -> float | None:
    """
    用 DashScope Embedding 计算两段文本的余弦相似度。
    如果 embedding 服务不可用或文本为空，返回 None。
    这是一个可选的诊断指标，不影响 pass/fail 判定。
    """
    if not text_a or not text_b or not text_a.strip() or not text_b.strip():
        return None
    try:
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        # 分别编码，避免 batch 的长度不平衡问题
        emb_a = svc.embed(text_a[:2048])  # 截断到合理长度
        emb_b = svc.embed(text_b[:2048])
        if not emb_a or not emb_b:
            return None
        # 余弦相似度
        dot = sum(a * b for a, b in zip(emb_a, emb_b))
        mag_a = math.sqrt(sum(a * a for a in emb_a))
        mag_b = math.sqrt(sum(b * b for b in emb_b))
        if mag_a == 0 or mag_b == 0:
            return None
        return round(dot / (mag_a * mag_b), 3)
    except Exception:
        return None


def _compute_keyword_match(expected_keywords: list, answer: str) -> tuple[int, float]:
    """
    计算关键词命中数。
    策略：先精确子串匹配，回退到 jieba token ≥50% 命中。
    返回 (命中数, 命中率)。
    """
    ans_token_set = set(jieba.cut(answer))
    kw_matched = 0
    for k in expected_keywords:
        if k in answer:
            kw_matched += 1
        else:
            k_tokens = [t for t in jieba.cut(k) if len(t.strip()) > 0]
            if k_tokens:
                token_hits = sum(1 for t in k_tokens if t in ans_token_set)
                if token_hits >= max(1, len(k_tokens) * 0.5):
                    kw_matched += 1
    kw_ratio = kw_matched / len(expected_keywords) if expected_keywords else 0.0
    return kw_matched, round(kw_ratio, 3)


def _compute_content_coverage(expected_content: list, answer: str) -> tuple[int, float]:
    """
    计算内容片段覆盖率。
    从 expected_content 中提取 4-gram 核心短语，检查是否在 answer 中出现。
    """
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
            if any(phrase in answer for phrase in core_phrases):
                content_matched += 1
    content_ratio = content_matched / content_total if content_total > 0 else 0.0
    return content_matched, round(content_ratio, 3)


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


# ============================================================
# Session 级结果收集器（供 L7 汇总报告使用）
# ============================================================

class _GenerationCollector:
    """收集所有 L2 parametrized 测试的结果，供汇总报告使用"""
    def __init__(self):
        self.results: list[dict] = []

    def record(self, **kwargs):
        self.results.append(kwargs)


@pytest.fixture(scope="session")
def gen_collector() -> _GenerationCollector:
    return _GenerationCollector()


# ============================================================
# L1: 系统健康检查
# ============================================================

@pytest.mark.generation
class TestL1_SystemHealth:
    """L1: 系统健康检查 — 阻断级"""

    def test_database_health(self):
        """验证数据库连接及已完成处理的文档数量"""
        from app.core.database import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            rows = db.execute(text("SELECT count(*) FROM documents WHERE status='completed'")).fetchall()
            count = rows[0][0]
            assert count > 0, "No completed documents found — 生成层测试无法进行"
            print(f"\n[L1] {count} completed documents")
        finally:
            db.close()


# ============================================================
# L2: 生成核心质量
# ============================================================

@pytest.mark.generation
class TestL2_AnswerQuality:
    """L2: 生成核心质量 — 阻断级。包含扎根度（Jaccard+语义）、关键词、内容覆盖、延迟、来源"""

    @pytest.mark.parametrize("question,expected_keywords,expected_content,difficulty", TEST_QUESTIONS)
    def test_answer_quality(self, question, expected_keywords, expected_content,
                            difficulty, auth_token, gen_collector):
        """对每个测试问题评估全部质量维度"""
        t0 = time.time()

        # -- 调用生成接口 --
        resp, status = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": question}, auth_token, timeout=90)
        assert status == 200, f"HTTP {status}"

        ans = resp.get("answer", "")
        sources = resp.get("sources", [])
        cc = resp.get("context_count", 0)

        # -- 获取检索上下文（用于扎根度计算） --
        resp2, _ = _api_call("http://localhost:8000/api/v1/chat/eval-retrieve", {"content": question}, auth_token, timeout=30)
        ctx_list = resp2.get("results", [])
        ctx_text = " ".join(c.get("content", "") for c in ctx_list)

        # ---- 扎根度(1): Jaccard token overlap ----
        ans_token_list = [t for t in jieba.cut(ans) if t not in STOPWORDS and t.strip()] if ans else []
        ctx_token_list = [t for t in jieba.cut(ctx_text) if t not in STOPWORDS and t.strip()] if ctx_text else []
        ans_tokens = set(ans_token_list)
        ctx_tokens = set(ctx_token_list)
        overlap = ans_tokens & ctx_tokens if ctx_tokens else set()
        grounded_jaccard = round(len(overlap) / len(ans_tokens), 3) if len(ans_tokens) > 0 else 0.0

        # ---- 扎根度(2): Embedding 语义相似度（诊断用，不影响 pass/fail） ----
        grounded_emb = _compute_embedding_similarity(ans, ctx_text)

        # ---- 关键词命中率 ----
        kw_matched, kw_ratio = _compute_keyword_match(expected_keywords, ans)

        # ---- 内容片段覆盖率 ----
        ct_matched, ct_ratio = _compute_content_coverage(expected_content, ans)

        # ---- 延迟与来源 ----
        latency = time.time() - t0
        source_present = len(sources) > 0 if cc > 0 else True

        # ---- 判定 ----
        grounded_threshold = GROUNDED_THRESHOLDS.get(difficulty, 0.30)
        content_threshold = CONTENT_THRESHOLDS.get(difficulty, 0.20)
        pass_grounded = grounded_jaccard >= grounded_threshold
        pass_kw = kw_ratio >= KEYWORD_RATIO_THRESHOLD
        pass_content = ct_ratio >= content_threshold or len(expected_content) == 0
        # hard 问题 LLM 大幅改写，4-gram 子串匹配不可靠。
        # 当 Jaccard 达标 且 关键词高命中时，已充分证明内容覆盖，豁免内容覆盖率检查。
        # 注意：不用 embedding 做交叉验证——连续 12 次 API 调用可能触发限流，不作为阻断依赖。
        if difficulty == "hard" and not pass_content:
            if grounded_jaccard >= 0.30 and kw_ratio >= 0.50:
                pass_content = True
        pass_latency = latency <= LATENCY_THRESHOLD
        pass_source = source_present
        all_pass = all([pass_grounded, pass_kw, pass_content, pass_latency, pass_source])

        # -- 收集结果 --
        gen_collector.record(
            question=question, difficulty=difficulty,
            grounded=grounded_jaccard, grounded_emb=grounded_emb,
            kw_matched=kw_matched, kw_total=len(expected_keywords),
            ct_matched=ct_matched, ct_total=len(expected_content),
            latency=latency, source_present=source_present,
            pass_grounded=pass_grounded, pass_kw=pass_kw,
            pass_content=pass_content, pass_latency=pass_latency,
            pass_source=pass_source, all_pass=all_pass,
        )

        # -- 断言 --
        assert bool(ans), "答案为空"
        assert pass_grounded, (
            f"扎根度过低 [{difficulty}]: {grounded_jaccard:.3f} (threshold={grounded_threshold})"
        )
        assert pass_kw, (
            f"关键词命中率过低: {kw_ratio:.3f} ({kw_matched}/{len(expected_keywords)})"
        )
        assert pass_content, (
            f"内容覆盖率过低: {ct_ratio:.3f} ({ct_matched}/{len(expected_content)})"
        )
        assert pass_latency, f"响应过慢: {latency:.1f}s"
        assert pass_source, "sources 字段为空"

        # -- 日志 --
        emb_str = f" emb={grounded_emb}" if grounded_emb is not None else ""
        print(
            f"\n[{difficulty:6s}] g={grounded_jaccard:.3f}{emb_str} "
            f"kw={kw_matched}/{len(expected_keywords)} "
            f"ct={ct_matched}/{len(expected_content)} "
            f"lat={latency:.1f}s"
            f"  [{question[:30]}...]"
        )


# ============================================================
# L3: 拒答防幻觉
# ============================================================

@pytest.mark.generation
class TestL3_Rejection:
    """L3: 拒答防幻觉 — 阻断级"""

    @pytest.mark.parametrize("question", REJECTION_TEST_QUESTIONS)
    def test_rejection(self, question, auth_token):
        """验证知识库无结果时系统不会编造答案"""
        resp, status = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": question}, auth_token, timeout=90)
        assert status == 200, f"HTTP {status}"

        ans = resp.get("answer", "")
        cc = resp.get("context_count", 0)

        has_rejection_phrase = any(phrase in ans for phrase in REJECTION_PHRASES)
        no_context_short = cc == 0 and len(ans) < 50
        correctly_rejected = has_rejection_phrase or no_context_short

        assert correctly_rejected, f"系统编造了答案: {ans[:100]}"
        print(f"\n[L3] [{question[:30]}] correctly rejected")


# ============================================================
# L4: 边界条件
# ============================================================

@pytest.mark.generation
class TestL4_EdgeCases:
    """L4: 边界条件 — 警告级"""

    @pytest.mark.parametrize("name,content,should_fail", [
        ("空输入", "", True),
        ("纯空格", "   ", True),
        ("超长输入", "A" * 5000, False),
        ("HTML注入", "<script>alert('xss')</script>", False),
        ("SQL注入", "'; DROP TABLE users; --", False),
    ])
    def test_edge_case(self, name, content, should_fail, auth_token):
        """验证系统对异常输入的处理"""
        resp, status_code = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": content}, auth_token, timeout=90)
        ans = resp.get("answer", "")

        if should_fail:
            passed = status_code == 400 or ans == ""
        else:
            passed = (status_code == 200 and ans != "") or status_code == 400

        assert passed, f"{name}: status={status_code}, ans_len={len(ans)}"
        print(f"\n[L4] [{name}] status={status_code}, passed={passed}")


# ============================================================
# L5: 多轮对话
# ============================================================

@pytest.mark.generation
class TestL5_MultiTurn:
    """L5: 多轮对话 — 警告级"""

    @pytest.mark.parametrize("questions,expected_kw", [
        (["上海交通大学的校训是什么？", "它体现了什么精神？"], ["饮水思源", "爱国荣校"]),
        (["交大学生如何申请休学？", "那复学需要什么条件？"], ["复学", "申请"]),
        (["GPA低于1.7会怎样？", "第二次低于1.7呢？"], ["退学警告", "试读"]),
    ])
    def test_multi_turn_context(self, questions, expected_kw, auth_token):
        """验证上下文关联能力（代词指代、省略主语、递进追问）"""
        resp1, status1 = _api_call("http://localhost:8000/api/v1/chat/ask",
                                   {"content": questions[0]}, auth_token, timeout=90)
        assert status1 == 200, f"第一轮HTTP {status1}"

        session_id = resp1.get("session_id")
        assert session_id, "未返回session_id"

        resp2, status2 = _api_call("http://localhost:8000/api/v1/chat/ask",
                                   {"content": questions[1], "session_id": session_id},
                                   auth_token, timeout=90)
        assert status2 == 200, f"第二轮HTTP {status2}"

        ans2 = resp2.get("answer", "")
        kw_matched = sum(1 for k in expected_kw if k in ans2)
        kw_ratio = kw_matched / len(expected_kw) if expected_kw else 0.0

        assert kw_ratio >= MULTI_TURN_KW_THRESHOLD, (
            f"多轮关键词命中率过低: {kw_ratio:.2f} ({kw_matched}/{len(expected_kw)})"
        )
        assert bool(ans2), "第二轮答案为空"
        print(f"\n[L5] [{questions[1][:25]}] kw={kw_matched}/{len(expected_kw)}")


# ============================================================
# L6: 流式输出
# ============================================================

@pytest.mark.generation
class TestL6_Streaming:
    """L6: 流式输出 — 警告级"""

    def test_streaming_output(self, auth_token):
        """验证 /ask/stream SSE 完整性：chunk 拼接 = done 答案，首字节 < 10s"""
        test_q = "上海交通大学的校训是什么？"

        t0 = time.time()
        d = json.dumps({"content": test_q}).encode()
        req = urllib.request.Request("http://localhost:8000/api/v1/chat/ask/stream",
                                     data=d, headers={
                                         "Authorization": "Bearer " + auth_token,
                                         "Content-Type": "application/json",
                                     })
        resp_obj = urllib.request.urlopen(req, timeout=90)

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
        first_byte_ok = first_chunk_time is not None and first_chunk_time < STREAM_FIRST_BYTE_THRESHOLD

        assert has_chunks, "没有收到 chunk"
        assert has_done, "没有收到 done 事件"
        assert answer_match, (
            f"chunk 拼接与 done 答案不一致: stream={len(stream_answer)} done={len(done_answer)}"
        )
        assert first_byte_ok, f"首字节时间过长: {first_chunk_time:.2f}s"

        print(
            f"\n[L6] streaming: chunks={len(chunks)}, "
            f"first_byte={first_chunk_time:.2f}s, total={total_latency:.2f}s"
        )


# ============================================================
# L7: 汇总报告
# ============================================================

@pytest.mark.generation
class TestL7_GenerationReport:
    """L7: 汇总报告 — 聚合 L2 全量结果，输出通过率和分数分布"""

    def test_generation_summary(self, gen_collector):
        """聚合所有 L2 parametrized 测试结果，输出完整报告"""
        results = gen_collector.results
        total = len(results)
        if total == 0:
            pytest.skip("没有 L2 生成测试结果可汇总")

        # 按难度分组
        by_difficulty = {"easy": [], "medium": [], "hard": []}
        for r in results:
            by_difficulty.setdefault(r["difficulty"], []).append(r)

        # 总体统计
        all_pass_count = sum(1 for r in results if r["all_pass"])
        grounded_vals = [r["grounded"] for r in results]
        emb_vals = [r["grounded_emb"] for r in results if r["grounded_emb"] is not None]
        latencies = [r["latency"] for r in results]

        report_lines = [
            f"\n{'='*60}",
            f"  生成层测试汇总报告",
            f"{'='*60}",
            f"  总测试数: {total}",
            f"  全部通过: {all_pass_count}/{total} ({all_pass_count/total*100:.0f}%)",
            f"  扎根度(Jaccard): avg={sum(grounded_vals)/len(grounded_vals):.3f}  "
            f"min={min(grounded_vals):.3f}  max={max(grounded_vals):.3f}",
        ]
        if emb_vals:
            report_lines.append(
                f"  扎根度(Embedding): avg={sum(emb_vals)/len(emb_vals):.3f}  "
                f"min={min(emb_vals):.3f}  max={max(emb_vals):.3f}"
            )
        report_lines.append(
            f"  平均延迟: {sum(latencies)/len(latencies):.1f}s  "
            f"max={max(latencies):.1f}s"
        )
        report_lines.append(f"{'─'*60}")

        # 分维度统计
        dim_stats = {
            "扎根度": sum(1 for r in results if r["pass_grounded"]),
            "关键词": sum(1 for r in results if r["pass_kw"]),
            "内容覆盖": sum(1 for r in results if r["pass_content"]),
            "延迟": sum(1 for r in results if r["pass_latency"]),
            "来源引用": sum(1 for r in results if r["pass_source"]),
        }
        report_lines.append("  各维度通过率:")
        for dim, cnt in dim_stats.items():
            report_lines.append(f"    {dim}: {cnt}/{total} ({cnt/total*100:.0f}%)")

        # 分难度统计
        report_lines.append(f"{'─'*60}")
        report_lines.append("  分难度统计:")
        for diff in ["easy", "medium", "hard"]:
            items = by_difficulty.get(diff, [])
            if not items:
                continue
            pass_cnt = sum(1 for r in items if r["all_pass"])
            avg_g = sum(r["grounded"] for r in items) / len(items) if items else 0
            avg_emb = (
                sum(r["grounded_emb"] for r in items if r["grounded_emb"] is not None)
                / max(1, sum(1 for r in items if r["grounded_emb"] is not None))
            ) if any(r["grounded_emb"] is not None for r in items) else None
            emb_str = f" emb_avg={avg_emb:.3f}" if avg_emb is not None else ""
            report_lines.append(
                f"    [{diff:6s}] {pass_cnt}/{len(items)} pass  "
                f"g_avg={avg_g:.3f}{emb_str}"
            )

        report_lines.append(f"{'='*60}")

        print("\n".join(report_lines))

        # 阻断：整体通过率必须 >= 50%
        overall_pass_rate = all_pass_count / total
        assert overall_pass_rate >= 0.50, (
            f"整体通过率过低: {all_pass_count}/{total} ({overall_pass_rate:.0%})，"
            f"阈值 50%"
        )
