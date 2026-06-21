"""
按 TOC 章节拆分 PDF 的核心函数
==============================
用于替换原有的按页拆分，实现按目录章节边界拆分为独立主题文档
使用 pdfplumber 提取文本（对中文 PDF 支持更好）
"""
import re
import os
import logging
from math import ceil

logger = logging.getLogger(__name__)

# 拆分策略阈值（与 documents.py 保持一致）
MIN_CHARS = 2000      # 章节过小合并阈值
MAX_CHARS = 200000    # 章节过大拆分阈值（仅处理异常巨大的章节）
TARGET_CHARS = 50000  # 目标单文档字符数（文件级拆分，非向量化分块）


def _extract_page_texts_with_pdfplumber(file_path: str, num_pages: int = 10) -> list:
    """
    使用 pdfplumber 提取 PDF 前 N 页文本（对中文支持更好）
    
    Args:
        file_path: PDF 文件路径
        num_pages: 提取的页数
        
    Returns:
        每页文本的列表
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber 未安装，回退到 PyPDF2")
        return None
    
    page_texts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for i in range(min(num_pages, len(pdf.pages))):
                text = pdf.pages[i].extract_text() or ""
                page_texts.append(text)
    except Exception as e:
        logger.warning(f"pdfplumber 提取失败: {e}")
        return None
    
    return page_texts


def _extract_page_texts_with_pypdf(file_path: str, num_pages: int = 10) -> list:
    """使用 PyPDF2 提取 PDF 前 N 页文本（回退方案）"""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            logger.warning("未找到 pypdf/PyPDF2")
            return []
    
    reader = PdfReader(file_path)
    page_texts = []
    for page in reader.pages[:num_pages]:
        text = page.extract_text() or ""
        page_texts.append(text)
    return page_texts


def parse_toc_entries(pdf_text_by_page: list) -> list:
    """
    从 PDF 页面文本中解析目录条目
    
    支持的格式：
    - "1 学生管理规定 …… 5"
    - "2 教学管理办法 …… 12"
    - "一、总则 …… 3"
    - "第一章 总则 …… 5"
    """
    entries = []
    current_category = ""
    
    # 多种目录格式的正则（使用贪婪匹配 .+ 确保标题完整捕获）
    toc_patterns = [
        # "1 标题 …… 页码" 或 "1. 标题 …… 页码"
        # 关键：使用 (.+) 贪婪匹配，然后 \s+(\d{1,3})$ 捕获末尾页码
        re.compile(r'^(\d{1,2})[\.、]?\s+(.+)\s+(\d{1,3})$'),
        # "一、标题 …… 页码"
        re.compile(r'^[一二三四五六七八九十]+[、\.]\s*(.+)\s+(\d{1,3})$'),
        # "第一章 标题 …… 页码"
        re.compile(r'^第[一二三四五六七八九十\d]+[章节篇部分]\s*(.+)\s+(\d{1,3})$'),
    ]
    
    for page_idx, page_text in enumerate(pdf_text_by_page):
        if not page_text:
            continue
        for line in page_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # 尝试匹配目录条目
            matched = False
            for pattern in toc_patterns:
                m = pattern.match(line)
                if m:
                    groups = m.groups()
                    
                    # 第一个正则 ^(\d{1,2})[\.、]?\s+(.+)\s+(\d{1,3})$ 有 3 个分组
                    # 其他正则只有 2 个分组
                    if pattern.pattern.startswith(r'^(\d'):
                        # groups: (编号, 标题, 页码)
                        number = int(groups[0])
                        title_str = groups[1].strip()
                        page_num = int(groups[2])
                    else:
                        # groups: (标题, 页码)
                        number = len(entries) + 1
                        title_str = groups[0].strip()
                        page_num = int(groups[1])
                    
                    # 去除标题末尾的 TOC 连接符（……、...、--- 等）
                    title_str = re.sub(r'[\s\.…\-—]+$', '', title_str).strip()
                    
                    entries.append({
                        "number": number,
                        "title": title_str,
                        "page_in_toc": page_num,
                        "category": current_category,
                        "toc_page_idx": page_idx,  # 记录TOC所在的页面索引
                    })
                    matched = True
                    break
            
            if not matched:
                # 尝试识别分类标题（短文本，无标点）
                if (not re.match(r'^\d', line) and 
                    "目录" not in line and " 录" not in line and
                    len(line) < 20 and 
                    not re.search(r'[，。；：、]', line)):
                    current_category = line
    
    return entries


def find_section_boundaries(reader, toc_entries: list) -> list:
    """
    根据 TOC 页码直接确定每个章节的页面范围
    
    不再逐页扫描匹配标题，而是直接使用目录中标注的页码：
    - 第 i 个章节：从 page_in_toc[i] 到 page_in_toc[i+1] - 1
    - 最后一个章节：从 page_in_toc[last] 到文档最后一页
    
    Args:
        reader: PdfReader 对象
        toc_entries: parse_toc_entries 返回的目录条目列表
    
    Returns:
        章节边界列表
    """
    total_pages = len(reader.pages)
    if not toc_entries:
        return []
    
    boundaries = []
    
    for i, entry in enumerate(toc_entries):
        # TOC 页码是 1-based，转换为 0-based 索引
        start_page = entry["page_in_toc"] - 1
        
        # 确定结束页：下一章起始页的前一页
        if i + 1 < len(toc_entries):
            end_page = toc_entries[i + 1]["page_in_toc"] - 2  # (page_in_toc - 1) - 1
        else:
            end_page = total_pages - 1  # 最后一个章节到文档末尾
        
        # 确保页码合法
        start_page = max(0, min(start_page, total_pages - 1))
        end_page = max(start_page, min(end_page, total_pages - 1))
        
        boundaries.append({
            "number": entry["number"],
            "title": entry["title"],
            "category": entry.get("category", ""),
            "start_page": start_page,
            "end_page": end_page,
        })
    
    return boundaries


def _safe_filename(base, num, title, category, ext):
    """生成安全的文件名"""
    prefix = f"{category}_" if category else ""
    clean = re.sub(r'[\\/*?:"<>|]', '', f"{prefix}{title}")
    return f"{base}_第{num:02d}章_{clean}{ext}"[:200]


def _estimate_section_chars(reader, start_page: int, end_page: int) -> int:
    """估算章节的字符数（采样前 3 页）"""
    sample_pages = min(3, end_page - start_page + 1)
    total_chars = 0
    for i in range(sample_pages):
        text = reader.pages[start_page + i].extract_text() or ""
        total_chars += len(text)
    # 按采样比例估算总字符数
    if sample_pages > 0:
        avg_chars_per_page = total_chars / sample_pages
        return int(avg_chars_per_page * (end_page - start_page + 1))
    return 0


def _split_or_merge_sections(reader, bounds: list, base: str, ext: str, dir_name: str) -> list:
    """
    对章节进行二次处理：
    - 章节 < 2000 字符 → 与相邻章节合并
    - 章节 > 200000 字符 → 二次拆分
    - 2000-200000 字符 → 保持原样
    """
    try:
        from pypdf import PdfWriter
    except ImportError:
        from PyPDF2 import PdfWriter
    
    # 估算每个章节的字符数
    section_info = []
    for b in bounds:
        if b["start_page"] > b["end_page"]:
            continue
        chars = _estimate_section_chars(reader, b["start_page"], b["end_page"])
        section_info.append({
            **b,
            "chars": chars,
        })
    
    # 日志输出章节大小
    for s in section_info:
        pages = s["end_page"] - s["start_page"] + 1
        logger.info(
            f"  [{s['number']:02d}] {s['title'][:30]} "
            f"(第{s['start_page']+1}-{s['end_page']+1}页, {pages}页, ~{s['chars']}字符)"
        )
    
    # 第一步：合并过小的章节（多轮迭代，直到没有可合并的）
    merged_sections = list(section_info)
    while True:
        newly_merged = []
        i = 0
        merged_this_round = False
        while i < len(merged_sections):
            current = merged_sections[i]
            
            # 如果当前章节太小，尝试与下一个合并
            if current["chars"] < MIN_CHARS and i + 1 < len(merged_sections):
                next_section = merged_sections[i + 1]
                merged = {
                    "number": current["number"],
                    "title": f"{current['title']} + {next_section['title']}",
                    "category": current.get("category", ""),
                    "start_page": current["start_page"],
                    "end_page": next_section["end_page"],
                    "chars": current["chars"] + next_section["chars"],
                }
                logger.info(
                    f"  合并: [{current['number']:02d}] + [{next_section['number']:02d}] "
                    f"(~{merged['chars']}字符)"
                )
                newly_merged.append(merged)
                i += 2
                merged_this_round = True
            else:
                newly_merged.append(current)
                i += 1
        merged_sections = newly_merged
        if not merged_this_round:
            break
    
    # 第二步：拆分过大的章节
    # 注意：拆分文件仅作为临时处理文件，MySQL 只存 1 条原始文档记录
    # 所以不需要限制拆分份数，按目标大小正常拆分即可
    
    final_sections = []
    for s in merged_sections:
        if s["chars"] <= MAX_CHARS:
            final_sections.append(s)
        else:
            # 需要二次拆分
            pages_in_section = s["end_page"] - s["start_page"] + 1
            avg_chars_per_page = s["chars"] / pages_in_section if pages_in_section > 0 else 1000
            avg_chars_per_page = avg_chars_per_page or 1000  # 防止除零
            
            # 计算需要拆几份
            pages_per_split = max(1, int(TARGET_CHARS / avg_chars_per_page))
            pages_per_split = min(pages_per_split, 20)  # 每份最多 20 页
            num_splits = ceil(pages_in_section / pages_per_split)
            
            logger.info(
                f"  拆分: [{s['number']:02d}] {s['title'][:30]} "
                f"(~{s['chars']}字符 → {num_splits} 份)"
            )
            
            for j in range(num_splits):
                split_start = s["start_page"] + j * pages_per_split
                split_end = min(s["start_page"] + (j + 1) * pages_per_split - 1, s["end_page"])
                final_sections.append({
                    "number": s["number"],
                    "title": f"{s['title']} (部分{j+1}/{num_splits})",
                    "category": s.get("category", ""),
                    "start_page": split_start,
                    "end_page": split_end,
                    "chars": int(avg_chars_per_page * (split_end - split_start + 1)),
                })
    
    # 第三步：生成 PDF 文件
    split_files = []
    for s in final_sections:
        if s["start_page"] > s["end_page"]:
            continue
        
        writer = PdfWriter()
        for p in range(s["start_page"], s["end_page"] + 1):
            writer.add_page(reader.pages[p])
        
        fname = _safe_filename(base, s["number"], s["title"], s.get("category", ""), ext)
        fpath = os.path.join(dir_name, fname)
        with open(fpath, "wb") as f:
            writer.write(f)
        split_files.append(fpath)
        
        pages = s["end_page"] - s["start_page"] + 1
        logger.info(
            f"    → {fname} (第{s['start_page']+1}-{s['end_page']+1}页, {pages}页, ~{s['chars']}字符)"
        )
    
    return split_files


def split_pdf_by_toc(file_path: str, original_filename: str) -> list:
    """
    按目录章节拆分 PDF，每个章节一个独立文档
    
    策略：
    1. 使用 pdfplumber 提取前 10 页文本（中文支持更好）
    2. 解析目录条目（编号、标题、页码）
    3. 直接使用 TOC 页码确定章节页面范围
    4. 对章节进行二次处理：
       - 章节 < 2000 字符 → 与相邻章节合并
       - 章节 > 200000 字符 → 二次拆分
       - 2000-200000 字符 → 保持原样
    5. 生成 PDF 文件
    """
    # 优先使用 pdfplumber 提取文本
    page_texts = _extract_page_texts_with_pdfplumber(file_path, num_pages=10)
    
    # 回退到 PyPDF2
    if page_texts is None:
        page_texts = _extract_page_texts_with_pypdf(file_path, num_pages=10)
    
    if not page_texts:
        logger.warning("无法提取 PDF 文本")
        return []
    
    logger.info(f"开始按 TOC 拆分: {original_filename}")
    
    # 获取总页数
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader
    
    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    
    if total_pages <= 50:
        logger.info(f"文档页数较少({total_pages}页)，跳过 TOC 拆分")
        return []
    
    # 解析 TOC
    toc = parse_toc_entries(page_texts)
    if len(toc) < 5:
        logger.warning(f"TOC 条目不足({len(toc)}), 回退按内容量拆分")
        return _fallback_split(reader, file_path, original_filename, total_pages)
    
    logger.info(f"解析到 {len(toc)} 个 TOC 条目")
    for e in toc:
        logger.info(f"  TOC: {e['number']}. {e['title']} -> 第 {e['page_in_toc']} 页")
    
    # 匹配章节边界
    bounds = find_section_boundaries(reader, toc)
    if len(bounds) < 2:
        logger.warning(f"章节边界不足({len(bounds)}), 回退按内容量拆分")
        return _fallback_split(reader, file_path, original_filename, total_pages)
    
    # 按章节拆分 + 二次处理（合并/拆分）
    dir_name = os.path.dirname(file_path)
    base = os.path.splitext(original_filename)[0]
    ext = os.path.splitext(original_filename)[1]
    
    logger.info(f"开始处理 {len(bounds)} 个章节...")
    split_files = _split_or_merge_sections(reader, bounds, base, ext, dir_name)
    
    logger.info(f"TOC 拆分完成: {len(split_files)} 个文档")
    return split_files


def _fallback_split(reader, file_path, original_filename, total_pages):
    """回退方案：按内容量拆分（推荐单文档 5000-10000 字符）"""
    from math import ceil
    try:
        from pypdf import PdfWriter
    except ImportError:
        from PyPDF2 import PdfWriter
    
    # 先估算每页平均字符数
    sample_pages = min(10, total_pages)
    total_sample_chars = 0
    for i in range(sample_pages):
        text = reader.pages[i].extract_text() or ""
        total_sample_chars += len(text)
    
    avg_chars_per_page = total_sample_chars / sample_pages if sample_pages > 0 else 1000
    avg_chars_per_page = avg_chars_per_page or 1000  # 防止除零
    
    # 目标：单文档约 8000 字符（与 TARGET_CHARS 一致）
    pages_per_doc = max(1, int(TARGET_CHARS / avg_chars_per_page))
    
    # 限制每份文档最多 20 页（避免单文档过大）
    pages_per_doc = min(pages_per_doc, 20)
    
    logger.info(f"回退拆分: 估算每页 {avg_chars_per_page:.0f} 字符，每份文档约 {pages_per_doc} 页")
    
    dir_name = os.path.dirname(file_path)
    base = os.path.splitext(original_filename)[0]
    ext = os.path.splitext(original_filename)[1]
    
    files = []
    num = ceil(total_pages / pages_per_doc)
    for i in range(num):
        s = i * pages_per_doc
        e = min((i + 1) * pages_per_doc, total_pages)
        writer = PdfWriter()
        for p in range(s, e):
            writer.add_page(reader.pages[p])
        fpath = os.path.join(dir_name, f"{base}_part{i+1:02d}{ext}")
        with open(fpath, "wb") as f:
            writer.write(f)
        files.append(fpath)
        logger.info(f"  拆分文档 {i+1}/{num}: 第{s+1}-{e}页 ({e-s}页)")
    
    return files
