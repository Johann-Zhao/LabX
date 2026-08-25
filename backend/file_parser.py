"""上传文件解析：把图片/PDF/Word/TXT 转成可喂给 LLM 的内容。

演示级实现：纯 Python，不依赖外部服务。
- 图片 → base64（前端已压缩到 1024px 以内，后端不再处理尺寸）
- PDF → pypdf 提取文本
- Word(docx) → python-docx 提取文本
- TXT/MD → 直接读取
"""
import base64
import os

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB，演示级限制

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_TEXT_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}
_EXT_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain", ".md": "text/markdown",
}


def guess_mime(filename: str, content_type: str | None = None) -> str:
    """优先用浏览器传的 Content-Type，其次按扩展名猜。"""
    if content_type and content_type != "application/octet-stream":
        return content_type
    ext = os.path.splitext(filename)[1].lower()
    return _EXT_MAP.get(ext, "application/octet-stream")


def parse_file(file_content: bytes, filename: str, content_type: str | None = None) -> dict:
    """解析上传文件，返回统一结构。

    返回格式：
    - 图片：{"ok": True, "type": "image", "base64": "...", "mime": "image/jpeg", "filename": "..."}
    - 文本：{"ok": True, "type": "text", "text": "...", "filename": "..."}
    - 错误：{"ok": False, "msg": "..."}
    """
    if len(file_content) > MAX_FILE_SIZE:
        return {"ok": False, "msg": f"文件超过 10MB 限制（当前 {len(file_content) // 1024 // 1024}MB）"}
    if len(file_content) == 0:
        return {"ok": False, "msg": "文件是空的（0 字节），请确认文件已保存内容后再上传"}

    mime = guess_mime(filename, content_type)

    if mime in _IMAGE_TYPES:
        return {
            "ok": True,
            "type": "image",
            "base64": base64.b64encode(file_content).decode("ascii"),
            "mime": mime,
            "filename": filename,
        }

    if mime == "application/pdf":
        return _parse_pdf(file_content, filename)

    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _parse_docx(file_content, filename)

    if mime in _TEXT_TYPES:
        try:
            text = file_content.decode("utf-8")
        except UnicodeDecodeError:
            text = file_content.decode("gbk", errors="replace")
        if not text.strip():
            return {"ok": False, "msg": "文件内容为空（全是空白字符），请补充有效内容后再上传"}
        return {"ok": True, "type": "text", "text": text, "filename": filename}

    return {"ok": False, "msg": f"不支持的文件格式：{mime}（支持图片/PDF/Word/TXT）"}


def _parse_pdf(file_content: bytes, filename: str) -> dict:
    """用 pypdf 提取 PDF 文本。"""
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(file_content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
        full = "\n\n".join(pages).strip()
        if not full:
            return {"ok": False, "msg": "PDF 内容为空或无法提取文本（可能是扫描件）"}
        return {"ok": True, "type": "text", "text": full, "filename": filename}
    except Exception as e:
        return {"ok": False, "msg": f"PDF 解析失败：{e}"}


def _parse_docx(file_content: bytes, filename: str) -> dict:
    """用 python-docx 提取 Word 文本。"""
    try:
        import docx
        from io import BytesIO

        doc = docx.Document(BytesIO(file_content))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        full = "\n".join(paragraphs).strip()
        if not full:
            return {"ok": False, "msg": "Word 文档内容为空"}
        return {"ok": True, "type": "text", "text": full, "filename": filename}
    except Exception as e:
        return {"ok": False, "msg": f"Word 解析失败：{e}"}
