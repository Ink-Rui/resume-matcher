"""
parser.py —— 文档文本解析模块

职责：把用户上传的简历文件（PDF / DOCX / TXT / MD）统一转成纯文本，
交给 matcher.py 做分析。

为什么要单独拆一个模块：
文件格式的差异（PDF 是二进制流、DOCX 是压缩包）和业务逻辑（匹配打分）
是两类完全不同的关注点。分开之后，将来要支持新格式（比如 PPT），
只需要在这里加一个分支，匹配逻辑一行都不用动。
"""

import io
import os
import zipfile
from xml.etree import ElementTree as ET

# Word 文档的 XML 命名空间
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def parse_upload(filename: str, data: bytes) -> str:
    """
    统一入口：根据文件扩展名，选择对应的解析方式。

    参数：
        filename —— 原始文件名（用于判断扩展名）
        data     —— 文件二进制内容
    返回：
        解析出的纯文本；解析失败时抛出 ValueError 并带明确原因。
    """
    ext = os.path.splitext(filename or "")[1].lower()

    if ext == ".pdf":
        return _parse_pdf(data)
    if ext == ".docx":
        return _parse_docx(data)
    if ext in (".txt", ".md", ".markdown"):
        return _parse_text(data)
    raise ValueError(f"暂不支持的文件格式：{ext or '未知'}。"
                     f"请上传 PDF、DOCX、TXT 或 MD 文件，或直接把简历内容粘贴到文本框。")


def _parse_text(data: bytes) -> str:
    """纯文本 / Markdown：直接解码。中文优先用 utf-8，失败则回退 gbk。"""
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _parse_pdf(data: bytes) -> str:
    """
    PDF：用 pypdf 逐页抽取文字。

    注意：扫描件（图片型 PDF）抽不出文字，这种情况会返回空字符串，
    上层会提示用户改用「粘贴文本」的方式。
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError("缺少 pypdf 库，请先执行：pip install -r requirements.txt")

    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            # 单页失败不影响整体，跳过即可
            pages.append("")

    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(
            "这个 PDF 里没有可提取的文字，很可能是「扫描件」（整页是图片）。"
            "请改用文本框直接粘贴简历内容，或换成 DOCX / TXT 格式。"
        )
    return text


def _parse_docx(data: bytes) -> str:
    """
    DOCX：它本质是一个 zip 包，正文在 word/document.xml 里。

    这里用标准库直接解析，不依赖第三方包，装起来最省事。
    会同时提取普通段落和表格里的文字——因为很多简历用表格排版，
    如果只读段落会漏掉大量内容。
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("文件不是有效的 DOCX，可能已损坏或实际是老版 .doc 格式。"
                         "老版 .doc 请先用 Word 另存为 .docx。")

    if "word/document.xml" not in zf.namelist():
        raise ValueError("DOCX 结构异常，找不到正文内容。")

    root = ET.fromstring(zf.read("word/document.xml"))
    body = root.find(_W_NS + "body")
    if body is None:
        return ""

    lines = []
    for el in body:
        tag = el.tag.replace(_W_NS, "")
        if tag == "p":
            # 普通段落
            text = "".join(t.text or "" for t in el.iter(_W_NS + "t")).strip()
            if text:
                lines.append(text)
        elif tag == "tbl":
            # 表格：逐行逐格拼接，单元格之间用空格分隔
            for row in el.findall(_W_NS + "tr"):
                cells = []
                for cell in row.findall(_W_NS + "tc"):
                    cell_text = " ".join(
                        "".join(t.text or "" for t in p.iter(_W_NS + "t")).strip()
                        for p in cell.findall(_W_NS + "p")
                    ).strip()
                    if cell_text:
                        cells.append(cell_text)
                if cells:
                    lines.append("  ".join(cells))

    return "\n".join(lines)


def summarize(text: str, limit: int = 120) -> str:
    """生成一段文本摘要，用于界面上的预览行。"""
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[:limit] + "…"
