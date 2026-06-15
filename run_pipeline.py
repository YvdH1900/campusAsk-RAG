"""Pipeline Runner"""

import sys, os, json, urllib.request
sys.path.insert(0, r"D:\Python Project\CampusAsk-RAG\backend")
sys.path.insert(0, r"D:\Python Project\CampusAsk-RAG\backend\tests")

LAYERS = ["Doc Status", "Chunk Quality", "BM25", "Intent+Expand", "Full Pipeline", "Golden Dataset"]
results = {}

def report():
    print()
    print("=" * 60)
    print("  Stage Report")
    print("=" * 60)
    diag = {
        "Doc Status": "Check if PDF uploaded and processed (status=completed)",
        "Chunk Quality": "Check TextSplitter params (parent chunks should be 20-300)",
        "BM25": "Check vector store data and BM25 tokenizer",
        "Intent+Expand": "Check intent_classifier rules and query_expansion dict",
        "Full Pipeline": "Check uvicorn running and eval-retrieve endpoint",
        "Golden Dataset": "Check keywords match actual PDF content",
    }
    passed = 0
    for i, name in enumerate(LAYERS, 1):
        r = results.get(name, {})
        if r.get("pass"):
            status = "PASS"
            info = r.get("info", "")
            passed += 1
        else:
            status = "FAIL"
            info = r.get("error", "not executed")
        print("  L" + str(i) + " [" + status + "] " + name + ": " + info)
    for name, msg in diag.items():
        r = results.get(name, {})
        if not r.get("pass"):
            print("  >>> " + name + ": " + msg)
    print("  Complete: " + str(passed) + "/" + str(len(LAYERS)))
    print("=" * 60)

def get_token():
    try:
        d = json.dumps({"username":"admin","password":"123456"}).encode()
        req = urllib.request.Request("http://localhost:8000/api/v1/auth/login", data=d, headers={"Content-Type":"application/json"})
        return json.loads(urllib.request.urlopen(req,timeout=5).read().decode()).get("access_token","")
    except:
        print("  [WARN] Backend offline, L4-L6 will be skipped")
        return None

def test_doc_status():
    from app.core.database import SessionLocal; from sqlalchemy import text
    db = SessionLocal()
    rows = db.execute(text("SELECT id,filename,status FROM documents WHERE status='completed' ORDER BY id")).fetchall()
    db.close()
    assert rows, "No completed documents found"
    r = rows[-1]
    return {"pass": True, "info": str(r[1]) + " [" + str(r[2]) + "]"}

def test_chunk_quality():
    from app.services.vector_store import VectorStore
    vs = VectorStore()
    res = vs.child_collection.query(expr="document_id>0", output_fields=["parent_id","child_content"], limit=10000)
    parents = set(r["parent_id"] for r in res)
    sizes = [len(r.get("child_content","")) for r in res]
    avg = sum(sizes)//len(sizes) if sizes else 0
    assert 20 <= len(parents) <= 300, "Parent count " + str(len(parents)) + " out of range"
    return {"pass":True, "info": str(len(res)) + " chunks | " + str(len(parents)) + " parents | avg=" + str(avg)}

def test_bm25():
    from app.services.vector_store import VectorStore
    from app.services.bm25_service import BM25Service
    vs = VectorStore()
    ents = vs.child_collection.query(expr="document_id>0", output_fields=["child_content"], limit=10000)
    if not ents:
        return {"pass":False, "error":"Vector store empty"}
    bm25 = BM25Service()
    bm25.build_index([e.get("child_content","") for e in ents])
    qs = ["\u6821\u8bad", "\u89c4\u5b9a", "\u4e49\u52a1"]
    counts = [len(bm25.search(q, top_k=10)) for q in qs]
    avg = sum(counts)/len(counts) if counts else 0
    if avg == 0:
        return {"pass":False, "error":"BM25 returned 0 after retry"}
    return {"pass":True, "info": str(len(qs)) + "Q avg=" + str(round(avg,1))}

def test_intent_and_expand(token):
    from app.services.intent_classifier import intent_classifier
    from app.services.query_expansion import QueryExpansionService
    cases = [("校训是什么","fact"),("怎么申请转专业","process"),("奖学金评选条件","policy")]
    correct = 0
    for q,e in cases:
        r = intent_classifier.classify(q)
        if r["intent"] == e: correct += 1
    eqs = ["义务","注册","奖学金","退学"]
    ex = 0
    for q in eqs:
        e = QueryExpansionService.expand_query_for_retrieval(q, use_ai=False)
        if e != q: ex += 1
    if correct < 2 or ex < 2:
        return {"pass":False, "error": "intent " + str(correct) + "/3 expand " + str(ex) + "/4"}
    return {"pass":True, "info": "intent " + str(correct) + "/3 expand " + str(ex) + "/4"}

def test_full_pipeline(token):
    qs = ["校训是什么","退学条件","奖学金评选"]
    passed = 0; total = 0
    for q in qs:
        d = json.dumps({"content":q}).encode()
        r = urllib.request.Request("http://localhost:8000/api/v1/chat/eval-retrieve",data=d,headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
        res = json.loads(urllib.request.urlopen(r,timeout=30).read().decode()).get("results",[])
        if len(res) > 0: passed += 1; total += len(res)
    if passed == 0:
        return {"pass":False, "error":"All queries returned 0 results"}
    return {"pass":True, "info": str(passed) + "/3 pass total " + str(total) + " items"}

def test_golden(token):
    from evaluation.retrieval_evaluator import RetrievalEvaluator
    from evaluation.golden_dataset import GOLDEN_DATASET
    ev = RetrievalEvaluator(top_k=5, use_mock=False)
    res = ev.evaluate(GOLDEN_DATASET)
    t = len(res); p = sum(1 for r in res if r.passed)
    recall = sum(r.recall for r in res)/t
    mrr = sum(r.mrr for r in res)/t
    prec = sum(r.precision for r in res)/t
    assert p/t > 0.85, "Pass rate " + str(p) + "/" + str(t) + " below 85%"
    return {"pass":True, "info": str(p) + "/" + str(t) + " pass recall=" + format(recall,".3f") + " mrr=" + format(mrr,".3f")}

def run():
    token = get_token()
    backend_ok = token is not None
    print("="*60)
    print("  Pipeline Test Runner")
    print("="*60)
    print()
    tests = [
        ("Doc Status", test_doc_status),
        ("Chunk Quality", test_chunk_quality),
        ("BM25", test_bm25),
        ("Intent+Expand", lambda: test_intent_and_expand(token) if backend_ok else {"pass":False,"error":"backend offline"}),
        ("Full Pipeline", lambda: test_full_pipeline(token) if backend_ok else {"pass":False,"error":"backend offline"}),
        ("Golden Dataset", lambda: test_golden(token) if backend_ok else {"pass":False,"error":"backend offline"}),
    ]
    for i, (name, func) in enumerate(tests, 1):
        print("  [" + str(i) + "/6] " + name + "...", end=" ", flush=True)
        try:
            r = func()
            results[name] = r
            if r["pass"]:
                print("PASS  " + r["info"])
            else:
                print("FAIL  " + r["error"])
                print("  >>> Stopped at L" + str(i))
                break
        except Exception as e:
            results[name] = {"pass":False, "error": str(e)[:80]}
            print("FAIL  " + str(e)[:80])
            print("  >>> Stopped at L" + str(i))
            break
    report()

if __name__ == "__main__":
    run()
