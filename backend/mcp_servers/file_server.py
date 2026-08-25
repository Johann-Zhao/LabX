"""file-mcp：文件处理 MCP Server。

FastMCP 薄封装，文件解析与上传审核逻辑复用 services.py / file_parser.py。
运行：python mcp_servers/file_server.py（stdio 传输，供编排引擎/评委检查调用）。
"""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from db import Upload, session_scope
from services import get_upload_core, list_uploads_core, review_upload_core

mcp = FastMCP("file-mcp")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")


@mcp.tool()
def parse_uploaded_file(upload_id: str) -> dict:
    """解析已上传的文件，返回文本内容或图片 base64。

    图片文件从磁盘读取并编码为 base64；文本文件直接返回解析后的文本。
    """
    with session_scope() as db:
        u = db.get(Upload, upload_id)
        if u is None:
            return {"error": f"上传记录 {upload_id} 不存在"}
        if u.file_type == "text":
            return {"type": "text", "text": u.parsed_text or "", "filename": u.filename}
        if u.file_type == "image":
            file_path = os.path.join(UPLOAD_DIR, os.path.basename(u.file_path))
            if not os.path.exists(file_path):
                return {"error": f"文件不存在：{file_path}"}
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            mime = "image/jpeg"
            if u.filename.lower().endswith(".png"):
                mime = "image/png"
            elif u.filename.lower().endswith(".gif"):
                mime = "image/gif"
            elif u.filename.lower().endswith(".webp"):
                mime = "image/webp"
            return {"type": "image", "base64": b64, "mime": mime, "filename": u.filename}
        return {"error": f"不支持的文件类型：{u.file_type}"}


@mcp.tool()
def get_pending_uploads() -> list[dict]:
    """获取待审核的上传资料列表（管理端用）。"""
    with session_scope() as db:
        res = list_uploads_core(db, status="pending")
        return res.get("data", [])


@mcp.tool()
def get_upload_detail(upload_id: str) -> dict:
    """获取单个上传记录的完整信息（含解析文本）。"""
    with session_scope() as db:
        return get_upload_core(db, upload_id)


@mcp.tool()
def approve_upload_to_knowledge(upload_id: str, note: str = "") -> dict:
    """审核通过上传资料，将其内容转为知识卡片并入向量库。"""
    with session_scope() as db:
        return review_upload_core(db, upload_id, approve=True, note=note)


@mcp.tool()
def reject_upload(upload_id: str, note: str = "") -> dict:
    """驳回上传资料，记录驳回理由。"""
    with session_scope() as db:
        return review_upload_core(db, upload_id, approve=False, note=note)


if __name__ == "__main__":
    mcp.run()
