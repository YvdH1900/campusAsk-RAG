"""测试 TOC 解析 + 页面匹配"""
import sys, glob, os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pdfplumber import open as pdf_open
from app.api.toc_splitter import parse_toc_entries

pattern = str(BACKEND_DIR / "uploads" / "documents" / "*part01*")
parts = sorted(glob.glob(pattern))
target = parts[0]

print(f"文件: {os.path.basename(target)}\n")

with pdf_open(target) as pdf:
    # TOC 解析
    page_texts = [pdf.pages[i].extract_text() or "" for i in range(10)]
    entries = parse_toc_entries(page_texts)
    print(f"TOC 共 {len(entries)} 个条目\n")

    # 页面匹配
    for e in entries:
        e["search_key"] = e["title"][:12].replace(" ", "").replace("\n", "")
    
    entry_idx = 0
    print("页面匹配 (前40页):")
    for page_idx in range(5, min(40, len(pdf.pages))):
        if entry_idx >= len(entries):
            break
        entry = entries[entry_idx]
        try:
            text = pdf.pages[page_idx].extract_text() or ""
        except Exception:
            text = ""
        text = text.replace(" ", "").replace("\n", "")
        if entry["search_key"] in text:
            print(f"  page {page_idx+1:3d} -> [{entry['number']:02d}] {entry['title'][:45]}")
            entry_idx += 1

    print(f"\n前40页匹配了 {entry_idx}/{len(entries)} 个条目")
    
    # 检查本科生管理规定在哪一页
    for i in range(min(20, len(pdf.pages))):
        text = pdf.pages[i].extract_text() or ""
        if "本科生管理规定" in text:
            print(f"\n'本科生管理规定' 出现在第 {i+1} 页")
            print(text[:200])
            break
