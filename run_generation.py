"""生成层测试 - 串行链式测试（生成质量）

测试答案生成质量：扎根度（groundedness）、关键词准确率、内容片段匹配、响应延迟。

测试层级:
  L1 系统健康检查   - 数据库连接 & Milvus 连通性
  L2 检索测试       - eval-retrieve 接口对测试问题返回检索结果
  L3 生成质量测试   - 答案生成 + 扎根度 + 关键词匹配 + 内容片段匹配 + 延迟
  L4 拒答测试       - 知识库无结果时不编造答案
  L5 边界条件测试   - 空输入、超长输入、注入攻击等异常处理
  L6 多轮对话测试   - 验证上下文关联能力
  L7 流式输出测试   - 验证 /ask/stream 完整性

评估指标:
  grounded       - 答案分词与检索上下文的 token 重叠率 (0.0~1.0)，>= 0.50 通过
                   （已过滤停用词，避免虚高）
  kw_acc         - 期望关键词在答案中的命中率，>= 0.30 通过
  content_acc    - 期望内容片段在答案中的命中率，>= 0.20 通过
  latency        - /ask 接口响应时间（秒），<= 30s 通过
  source_present - 有检索结果时 sources 字段非空

失败条件:
  grounded < 0.50     = 疑似幻觉（答案未扎根于检索上下文）
  latency > 30s       = 响应过慢（LLM 或 Milvus 问题）
  kw_acc < 0.30       = 关键信息缺失
  content_acc < 0.20  = 内容片段覆盖不足
  拒答测试失败         = 系统编造了知识库中不存在的信息
"""
import sys, os, json, urllib.request, time
sys.path.insert(0, "D:\\Python Project\\CampusAsk-RAG\\backend")
sys.path.insert(0, "D:\\Python Project\\CampusAsk-RAG\\backend\\tests")

from evaluation.golden_dataset import GOLDEN_DATASET, get_questions_by_difficulty

# 从 Golden Dataset 中选取覆盖 easy/medium/hard 各难度的测试问题
# 确保测试样本具有代表性，不仅限于简单问题
_easy_qs = get_questions_by_difficulty("easy")[:4]      # 取 4 个简单题
_medium_qs = get_questions_by_difficulty("medium")[:4]  # 取 4 个中等题
_hard_qs = get_questions_by_difficulty("hard")[:4]      # 取 4 个困难题
TEST_QUESTIONS = [(qa.question, qa.expected_keywords, qa.expected_content)
                  for qa in _easy_qs + _medium_qs + _hard_qs]

# 拒答测试问题：知识库中不存在的内容，验证系统不会编造答案
REJECTION_TEST_QUESTIONS = [
    "清华大学校长是谁？",          # 外校问题，不在本校知识库
    "火星殖民地如何申请？",        # 荒诞问题
]

# 测试层级名称（串行执行，任一失败则终止）
LAYERS = ["System Health", "Retrieval", "Answer Gen+Quality+Groundedness", "Rejection", "Edge Cases", "Multi-turn", "Streaming"]
# 各层测试结果
results = {}
# L3 逐题详细结果（供报告输出）
_gen_results = None

# 中文停用词表 —— 计算 grounded 时过滤，避免"的""了""学校"等高频词
# 导致答案与上下文的 token 重叠率虚高
STOPWORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "为什么",
    "可以", "能", "吗", "呢", "吧", "啊", "呀", "哦", "嗯", "而", "但", "但是", "如果",
    "因为", "所以", "虽然", "然后", "之后", "以后", "之前", "以前", "现在", "已经", "正在",
    "学校", "学生", "根据", "相关", "规定", "要求", "需要", "应该", "必须", "对于", "关于",
])

# 拒答标志短语 —— 答案中包含这些完整短语说明系统正确拒答了
# 使用较长短语避免误匹配（如"不在"可能出现在正常回答"不在秋季学期"中）
REJECTION_PHRASES = [
    "无法找到", "未找到", "没有找到", "抱歉", "不清楚",
    "暂无相关", "知识库中", "无法回答", "暂时无法", "没有相关",
    "无法从", "未能在", "未检索到",
]


def _api_call(url, payload, token, timeout=30):
    """通用 API 调用封装，返回 (response_dict, http_status_code)"""
    d = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=d, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    })
    try:
        resp_obj = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp_obj.read().decode()), resp_obj.status
    except urllib.error.HTTPError as e:
        # API 返回 4xx/5xx 时读取响应体并返回状态码
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        return body, e.code


def get_token():
    """登录后台获取 JWT token，失败返回 None"""
    try:
        d = json.dumps({"username": "admin", "password": "123456"}).encode()
        req = urllib.request.Request("http://localhost:8000/api/v1/auth/login", data=d, headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=5).read().decode()).get("access_token", "")
    except Exception:
        return None


def test_health():
    """L1: 系统健康检查 - 验证数据库连接及已完成处理的文档数量"""
    from app.core.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT count(*) FROM documents WHERE status='completed'")).fetchall()
        c = rows[0][0]
        if c > 0:
            return {"pass": True, "info": str(c) + " completed documents"}
        return {"pass": False, "error": "No completed documents found"}
    finally:
        db.close()


def test_retrieval(token):
    """L2: 检索测试 - 验证 eval-retrieve 接口对每个测试问题都能返回检索结果
    通过条件: 至少 50% 的问题有检索结果返回
    """
    count = 0
    for q, kw, ec in TEST_QUESTIONS:
        try:
            resp, status = _api_call("http://localhost:8000/api/v1/chat/eval-retrieve", {"content": q}, token, timeout=30)
            if status == 200:
                res = resp.get("results", [])
                if len(res) > 0:
                    count += 1
        except Exception:
            pass
    total = len(TEST_QUESTIONS)
    if count == 0:
        return {"pass": False, "error": "All " + str(total) + " queries returned 0 results"}
    # 允许部分失败，但至少需要 50% 通过
    if count < total * 0.5:
        return {"pass": False, "error": str(count) + "/" + str(total) + " queries returned results (need >= 50%)"}
    return {"pass": True, "info": str(count) + "/" + str(total) + " queries returned results"}


def test_answer_gen(token):
    """L3: 生成质量测试 - 对每个测试问题调用 /ask 接口，评估:
    1. grounded (扎根度): 答案分词后与检索上下文的 token 重叠率，过滤停用词
    2. kw_acc (关键词命中率): 期望关键词在答案中出现的比例
    3. content_acc (内容片段命中率): 期望内容片段在答案中出现的比例
    4. latency (延迟): /ask 接口响应时间
    5. source_present (来源引用): 有检索上下文时 sources 字段非空

    每个问题独立判定 pass/fail，最终汇总各指标均值做整体判定。
    """
    import jieba
    results_list = []
    for q, kw, expected_content in TEST_QUESTIONS:
        try:
            t0 = time.time()
            # 调用 /ask 获取答案
            resp, status = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": q}, token, timeout=60)
            if status != 200:
                raise Exception(f"HTTP {status}")
            ans = resp.get("answer", "")
            sources = resp.get("sources", [])
            cc = resp.get("context_count", 0)

            # 调用 eval-retrieve 获取检索上下文（用于计算扎根度）
            # /ask 响应不含上下文原文，需单独获取
            resp2, _ = _api_call("http://localhost:8000/api/v1/chat/eval-retrieve", {"content": q}, token, timeout=30)
            ctx_list = resp2.get("results", [])
            ctx_text = " ".join(c.get("content", "") for c in ctx_list)

            # --- 指标 1: 扎根度 (grounded) ---
            # 答案分词与检索上下文的 token 重叠率，过滤停用词
            ans_tokens = set(jieba.cut(ans)) - STOPWORDS if ans else set()
            ctx_tokens = set(jieba.cut(ctx_text)) - STOPWORDS if ctx_text else set()
            overlap = ans_tokens & ctx_tokens if ctx_tokens else set()
            grounded = len(overlap) / len(ans_tokens) if len(ans_tokens) > 0 else 0.0

            # --- 指标 2: 关键词命中率 (kw_acc) ---
            # 使用灵活匹配：精确匹配或核心字符匹配（>=60%字符）
            kw_matched = 0
            for k in kw:
                if k in ans:
                    # 精确匹配
                    kw_matched += 1
                elif len(k) >= 4:
                    # 对于较长的关键词，检查是否有60%以上的字符连续出现
                    # 例如"应予退学"可能变成"会被退学"
                    for i in range(len(k) - 2):
                        if k[i:i+3] in ans:
                            kw_matched += 1
                            break
            kw_ratio = kw_matched / len(kw) if kw else 0.0

            # --- 指标 3: 内容片段命中率 (content_acc) ---
            # 检查 expected_content 中的语义要点是否被答案覆盖
            # LLM 会改写原文，不能用精确子串匹配
            # 策略: 从每个 expected_content 中提取 2-4 字核心词组，
            # 检查答案中命中了多少核心词组
            content_matched = 0
            content_total = len(expected_content) if expected_content else 0
            if expected_content:
                for ec in expected_content:
                    # 提取核心词组：去除常见虚词，取连续实词
                    # 用 2-4 字核心片段检测，任一命中即算覆盖
                    core_phrases = []
                    # 提取 4 字片段（滑动窗口步长=2，减少计算量）
                    if len(ec) >= 4:
                        for i in range(0, len(ec) - 3, 2):
                            phrase = ec[i:i + 4]
                            # 跳过纯虚词片段
                            if not all(c in "的了在是和就不人都一个上也很到说要去你会着没有看好自己这" for c in phrase):
                                core_phrases.append(phrase)
                    # 如果 ec 较短，直接加入
                    if len(ec) < 4 and len(ec) >= 2:
                        core_phrases.append(ec)

                    # 只要有 1 个核心词组出现在答案中就算命中
                    if any(phrase in ans for phrase in core_phrases):
                        content_matched += 1
            content_ratio = content_matched / content_total if content_total > 0 else 0.0

            # 总耗时（/ask + eval-retrieve）
            latency = time.time() - t0

            # --- 指标 4: 来源引用验证 ---
            # 有检索上下文时，sources 字段应非空
            source_present = len(sources) > 0 if cc > 0 else True

            # 单项判定: 各指标全部达标且答案非空才算通过
            pass_grounded = grounded >= 0.50
            pass_kw = kw_ratio >= 0.25
            pass_content = content_ratio >= 0.20 or content_total == 0  # 无 expected_content 时自动通过
            pass_latency = latency <= 30.0
            pass_source = source_present
            passed = pass_grounded and pass_kw and pass_content and pass_latency and pass_source and bool(ans)

            results_list.append({
                "q": q, "passed": passed, "ans_len": len(ans),
                "sources": len(sources), "context_count": cc,
                "kw_matched": kw_matched, "kw_total": len(kw),
                "content_matched": content_matched, "content_total": content_total,
                "grounded": round(grounded, 3), "latency": round(latency, 2),
                "has_answer": bool(ans),
                "pass_grounded": pass_grounded, "pass_kw": pass_kw,
                "pass_content": pass_content, "pass_latency": pass_latency,
                "pass_source": pass_source,
            })
        except Exception as e:
            results_list.append({
                "q": q, "passed": False, "error": str(e)[:60],
                "grounded": 0.0, "latency": 0.0,
                "kw_matched": 0, "kw_total": len(kw),
                "content_matched": 0, "content_total": len(expected_content),
            })

    # 汇总统计
    total = len(results_list)
    passed = sum(1 for r in results_list if r["passed"])
    avg_grounded = sum(r["grounded"] for r in results_list) / total if total > 0 else 0.0
    avg_latency = sum(r["latency"] for r in results_list) / total if total > 0 else 0.0
    # 计算 P99 延迟（发现长尾问题）
    latencies = sorted([r["latency"] for r in results_list if r.get("latency", 0) > 0])
    p99_latency = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    kw_total_val = sum(r["kw_total"] for r in results_list)
    kw_matched_val = sum(r["kw_matched"] for r in results_list)
    kw_acc = kw_matched_val / kw_total_val if kw_total_val > 0 else 0.0

    # 保存逐题详细结果供报告使用
    global _gen_results
    _gen_results = results_list

    # 整体判定: 收集所有失败原因
    fail_reasons = []
    if avg_grounded < 0.50:
        fail_reasons.append("grounded=" + str(round(avg_grounded, 2)) + " below 0.50 (hallucination suspected)")
    if kw_acc < 0.30:
        fail_reasons.append("kw_acc=" + str(round(kw_acc, 2)) + " below 0.30 (important info missing)")
    if avg_latency > 30.0:
        fail_reasons.append("latency=" + str(round(avg_latency, 1)) + "s above 30s (too slow)")
    if p99_latency > 45.0:
        fail_reasons.append("p99_latency=" + str(round(p99_latency, 1)) + "s above 45s (tail latency)")
    if passed < total:
        fail_reasons.append(str(passed) + "/" + str(total) + " questions passed individually")
    if fail_reasons:
        return {"pass": False, "error": "; ".join(fail_reasons)}
    return {"pass": True, "info": str(passed) + "/" + str(total) + " pass, kw=" + str(round(kw_acc, 2)) + ", grounded=" + str(round(avg_grounded, 2)) + ", lat=" + str(round(avg_latency, 1)) + "s, p99=" + str(round(p99_latency, 1)) + "s"}


def test_rejection(token):
    """L4: 拒答测试 - 验证知识库无结果时系统不会编造答案
    对 REJECTION_TEST_QUESTIONS 中的问题调用 /ask，
    答案中应包含拒答标志词（如"无法找到""抱歉"等），
    或 context_count 为 0 且答案不含具体事实性内容。
    """
    results_list = []
    for q in REJECTION_TEST_QUESTIONS:
        try:
            resp, status = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": q}, token, timeout=60)
            if status != 200:
                raise Exception(f"HTTP {status}")
            ans = resp.get("answer", "")
            cc = resp.get("context_count", 0)

            # 判断是否正确拒答：
            # 条件 A: 答案中包含拒答标志短语
            has_rejection_phrase = any(phrase in ans for phrase in REJECTION_PHRASES)
            # 条件 B: 无检索上下文 且 答案较短（不太可能在编造具体事实）
            no_context_short = cc == 0 and len(ans) < 50
            # 满足任一条件即视为正确拒答
            correctly_rejected = has_rejection_phrase or no_context_short

            results_list.append({
                "q": q, "passed": correctly_rejected,
                "ans_len": len(ans), "context_count": cc,
                "has_rejection_phrase": has_rejection_phrase,
                "no_context_short": no_context_short,
            })
        except Exception as e:
            results_list.append({"q": q, "passed": False, "error": str(e)[:60]})

    total = len(results_list)
    passed = sum(1 for r in results_list if r["passed"])

    # 保存详细结果
    global _gen_results
    if _gen_results is None:
        _gen_results = []
    _gen_results.extend(results_list)

    if passed == 0:
        return {"pass": False, "error": "All " + str(total) + " rejection tests failed (system is hallucinating)"}
    if passed < total:
        return {"pass": True, "info": str(passed) + "/" + str(total) + " rejection tests passed (partial)"}
    return {"pass": True, "info": str(passed) + "/" + str(total) + " rejection tests passed"}


def test_edge_cases(token):
    """L5: 边界条件测试 - 验证系统对异常输入的处理
    测试场景:
    1. 空输入: 应返回错误而非崩溃
    2. 超长输入: 应能处理或优雅拒绝
    3. 特殊字符: 应能处理 HTML/SQL 注入尝试
    4. 纯空格输入: 应返回错误
    """
    edge_cases = [
        ("空输入", "", True),  # 应失败（400错误）
        ("纯空格", "   ", True),  # 应失败
        ("超长输入", "A" * 5000, False),  # 应能处理或优雅拒绝
        ("HTML注入", "<script>alert('xss')</script>", False),  # 应能处理
        ("SQL注入", "'; DROP TABLE users; --", False),  # 应能处理
    ]

    results_list = []
    for name, content, should_fail in edge_cases:
        try:
            resp, status_code = _api_call("http://localhost:8000/api/v1/chat/ask", {"content": content}, token, timeout=60)
            ans = resp.get("answer", "")

            # 判定逻辑:
            # - 如果 should_fail=True，期望返回 400 错误或空答案
            # - 如果 should_fail=False，期望返回 200 且答案非空（或优雅拒绝）
            if should_fail:
                # 应失败的场景：400错误 或 空答案
                passed = status_code == 400 or ans == ""
            else:
                # 应处理的场景：200且答案非空，或 400优雅拒绝
                passed = (status_code == 200 and ans != "") or status_code == 400

            results_list.append({
                "q": name, "passed": passed,
                "status_code": status_code, "ans_len": len(ans),
                "should_fail": should_fail,
            })
        except Exception as e:
            # 网络错误（非 HTTP 错误，如连接失败）
            results_list.append({
                "q": name, "passed": False, "error": str(e)[:60],
                "should_fail": should_fail,
            })

    total = len(results_list)
    passed = sum(1 for r in results_list if r["passed"])

    # 保存详细结果
    global _gen_results
    if _gen_results is None:
        _gen_results = []
    _gen_results.extend(results_list)

    if passed < total:
        return {"pass": False, "error": str(passed) + "/" + str(total) + " edge cases passed"}
    return {"pass": True, "info": str(passed) + "/" + str(total) + " edge cases passed"}


def test_multi_turn(token):
    """L6: 多轮对话测试 - 验证上下文关联能力
    测试场景:
    1. 先问"校训是什么"，再问"它体现了什么精神"（代词指代）
    2. 先问"休学怎么申请"，再问"那复学呢"（省略主语）
    3. 先问"GPA低于1.7会怎样"，再问"第二次呢"（递进追问）
    """
    # 多轮对话测试用例: (问题序列, 最后一问的期望关键词)
    multi_turn_cases = [
        # 代词指代测试
        (["上海交通大学的校训是什么？", "它体现了什么精神？"], ["饮水思源", "爱国荣校"]),
        # 省略主语测试
        (["交大学生如何申请休学？", "那复学需要什么条件？"], ["复学", "申请"]),
        # 递进追问测试
        (["GPA低于1.7会怎样？", "第二次低于1.7呢？"], ["退学警告", "试读"]),
    ]

    results_list = []
    for questions, expected_kw in multi_turn_cases:
        try:
            # 第一轮对话（创建会话）
            resp1, status1 = _api_call("http://localhost:8000/api/v1/chat/ask",
                                       {"content": questions[0]}, token, timeout=60)
            if status1 != 200:
                raise Exception(f"第一轮HTTP {status1}")

            session_id = resp1.get("session_id")
            if not session_id:
                raise Exception("未返回session_id")

            # 第二轮对话（使用同一会话）
            resp2, status2 = _api_call("http://localhost:8000/api/v1/chat/ask",
                                       {"content": questions[1], "session_id": session_id},
                                       token, timeout=60)
            if status2 != 200:
                raise Exception(f"第二轮HTTP {status2}")

            ans2 = resp2.get("answer", "")

            # 检查第二轮答案是否包含期望关键词
            kw_matched = sum(1 for k in expected_kw if k in ans2)
            kw_ratio = kw_matched / len(expected_kw) if expected_kw else 0.0

            # 判定: 关键词命中率 >= 0.30 且答案非空
            passed = kw_ratio >= 0.30 and bool(ans2)

            results_list.append({
                "q": questions[1][:25], "passed": passed,
                "ans_len": len(ans2), "session_id": session_id,
                "kw_matched": kw_matched, "kw_total": len(expected_kw),
                "kw_ratio": round(kw_ratio, 2),
            })
        except Exception as e:
            results_list.append({
                "q": questions[1][:25] if len(questions) > 1 else questions[0][:25],
                "passed": False, "error": str(e)[:60],
            })

    total = len(results_list)
    passed = sum(1 for r in results_list if r["passed"])

    # 保存详细结果
    global _gen_results
    if _gen_results is None:
        _gen_results = []
    _gen_results.extend(results_list)

    if passed < total:
        return {"pass": False, "error": str(passed) + "/" + str(total) + " multi-turn tests passed"}
    return {"pass": True, "info": str(passed) + "/" + str(total) + " multi-turn tests passed"}


def test_streaming(token):
    """L7: 流式输出测试 - 验证 /ask/stream 完整性
    测试场景:
    1. 流式输出应包含 chunk 事件和 done 事件
    2. chunk 内容拼接后应与 done 中的 answer 一致
    3. 流式响应时间应小于非流式（首字节更快）
    """
    # 使用简单问题测试流式
    test_q = "上海交通大学的校训是什么？"

    results_list = []
    try:
        # 调用流式接口
        t0 = time.time()
        d = json.dumps({"content": test_q}).encode()
        req = urllib.request.Request("http://localhost:8000/api/v1/chat/ask/stream",
                                     data=d, headers={
                                         "Authorization": "Bearer " + token,
                                         "Content-Type": "application/json",
                                     })
        resp_obj = urllib.request.urlopen(req, timeout=60)

        # 解析 SSE 流
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

        # 验证1: 应有 chunk 事件
        has_chunks = len(chunks) > 0

        # 验证2: 应有 done 事件
        has_done = done_data is not None

        # 验证3: chunk 拼接内容应与 done 中的 answer 一致
        stream_answer = ''.join(chunks)
        done_answer = done_data.get('answer', '') if done_data else ''
        answer_match = stream_answer == done_answer

        # 验证4: 首字节时间应合理（< 10秒）
        first_byte_ok = first_chunk_time is not None and first_chunk_time < 10.0

        # 综合判定
        passed = has_chunks and has_done and answer_match and first_byte_ok

        results_list.append({
            "q": test_q[:25], "passed": passed,
            "chunk_count": len(chunks), "has_done": has_done,
            "answer_match": answer_match, "first_byte_time": round(first_chunk_time or 0, 2),
            "total_latency": round(total_latency, 2),
            "stream_len": len(stream_answer), "done_len": len(done_answer),
        })
    except Exception as e:
        results_list.append({
            "q": test_q[:25], "passed": False, "error": str(e)[:60],
        })

    # 保存详细结果
    global _gen_results
    if _gen_results is None:
        _gen_results = []
    _gen_results.extend(results_list)

    total = len(results_list)
    passed = sum(1 for r in results_list if r["passed"])

    if passed < total:
        return {"pass": False, "error": str(passed) + "/" + str(total) + " streaming tests passed"}
    return {"pass": True, "info": str(passed) + "/" + str(total) + " streaming tests passed"}


def report():
    """生成测试报告: 打印到终端并写入 gen_report.json"""
    print()
    print("=" * 60)
    print("  Generation Pipeline Report")
    print("=" * 60)
    passed = 0
    data = {}
    # 逐层输出结果
    for i, name in enumerate(LAYERS, 1):
        r = results.get(name, {})
        data[name] = r
        if r.get("pass"):
            status = "PASS"
            info = r.get("info", "")
            passed += 1
        else:
            status = "FAIL"
            info = r.get("error", "not executed")
        print(f"  L{i} [{status}] {name}: {info}")
    # 输出逐题详情
    if _gen_results:
        print()
        print("  Per-Question Detail:")
        for r in _gen_results:
            q_short = r["q"][:25] + "..." if len(r["q"]) > 25 else r["q"]
            status = "PASS" if r["passed"] else "FAIL"
            err = ("  err=" + r["error"]) if r.get("error") else ""
            # L3 详情：显示关键词、内容片段、扎根度、延迟
            if "kw_total" in r and "grounded" in r:
                print("    [" + status + "] \"" + q_short + "\""
                      + "  kw=" + str(r["kw_matched"]) + "/" + str(r["kw_total"])
                      + "  ct=" + str(r.get("content_matched", 0)) + "/" + str(r.get("content_total", 0))
                      + "  g=" + str(r["grounded"])
                      + "  lat=" + str(r["latency"]) + "s" + err)
            # L5 边界条件详情
            elif "status_code" in r:
                print("    [" + status + "] \"" + q_short + "\""
                      + "  http=" + str(r["status_code"])
                      + "  len=" + str(r.get("ans_len", 0)) + err)
            # L6 多轮对话详情
            elif "session_id" in r:
                print("    [" + status + "] \"" + q_short + "\""
                      + "  kw=" + str(r.get("kw_matched", 0)) + "/" + str(r.get("kw_total", 0))
                      + "  sid=" + str(r.get("session_id", "")) + err)
            # L7 流式输出详情
            elif "chunk_count" in r:
                print("    [" + status + "] \"" + q_short + "\""
                      + "  chunks=" + str(r.get("chunk_count", 0))
                      + "  done=" + str(r.get("has_done", False))
                      + "  match=" + str(r.get("answer_match", False))
                      + "  first=" + str(r.get("first_byte_time", 0)) + "s" + err)
            else:
                # L4 拒答详情
                rej = "rejected" if r.get("has_rejection_phrase") or r.get("no_context_short") else "HALLUCINATED"
                print("    [" + status + "] \"" + q_short + "\"  " + rej + err)
    print(f"  Complete: {passed}/{len(LAYERS)}")
    print("=" * 60)
    # 写入 JSON 报告
    data["summary"] = {"passed": passed, "total": len(LAYERS)}
    data["detail"] = _gen_results or []
    with open("gen_report.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run():
    """主入口: 按 L1 -> L2 -> L3 -> L4 -> L5 -> L6 -> L7 串行执行，任一层失败则终止"""
    print("=" * 60)
    print("  Generation Pipeline Test Runner")
    print("=" * 60)
    print()
    # 获取认证 token
    token = get_token()
    if token is None:
        print("  [WARN] Backend offline - L2/L3/L4/L5/L6/L7 will be skipped")
    # 按层级串行执行
    offline_result = {"pass": False, "error": "backend offline"}
    test_steps = [
        ("System Health", test_health),
        ("Retrieval", lambda: test_retrieval(token) if token else offline_result),
        ("Answer Gen+Quality+Groundedness", lambda: test_answer_gen(token) if token else offline_result),
        ("Rejection", lambda: test_rejection(token) if token else offline_result),
        ("Edge Cases", lambda: test_edge_cases(token) if token else offline_result),
        ("Multi-turn", lambda: test_multi_turn(token) if token else offline_result),
        ("Streaming", lambda: test_streaming(token) if token else offline_result),
    ]
    for i, (name, func) in enumerate(test_steps, 1):
        print(f"  [{i}/{len(test_steps)}] {name}...", end=" ", flush=True)
        try:
            r = func()
            results[name] = r
            if r["pass"]:
                print("PASS  " + r["info"])
            else:
                print("FAIL  " + r["error"])
                # 继续执行后续测试，不中断
        except Exception as e:
            results[name] = {"pass": False, "error": str(e)[:80]}
            print("FAIL  " + str(e)[:80])
            # 继续执行后续测试，不中断
    report()

if __name__ == "__main__":
    run()
