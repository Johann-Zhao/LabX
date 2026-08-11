"""knowledge-mcp：知识服务 MCP Server。

FastMCP 薄封装，RAG 问答复用 services.ask_core（Chroma 检索 + LLM 生成）。
运行：python mcp_servers/knowledge_server.py（stdio 传输，供编排引擎/评委检查调用）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from db import KnowledgeCard, SessionLocal
from services import ask_core, experience_core

mcp = FastMCP("knowledge-mcp")


@mcp.tool()
def get_knowledge_card(material_id: str, card_type: str = "") -> list[dict]:
    """获取指定物料的知识卡片。card_type 可过滤：manual/quickstart/common_errors/tip。"""
    db = SessionLocal()
    try:
        q = db.query(KnowledgeCard).filter(KnowledgeCard.material_id == material_id)
        if card_type:
            q = q.filter(KnowledgeCard.card_type == card_type)
        return [
            {
                "card_id": c.id,
                "card_type": c.card_type,
                "title": c.title,
                "points": json.loads(c.points),
                "content": c.content,
            }
            for c in q.all()
        ]
    finally:
        db.close()


@mcp.tool()
def query_knowledge_base(question: str, material_id: str | None = None) -> dict:
    """基于 RAG 的开放式知识问答，返回答案与引用卡片。material_id 可限定物料上下文。"""
    return ask_core(question, material_id)


@mcp.tool()
def share_experience(material_id: str, user_id: str, content: str) -> dict:
    """提交使用经验：LLM 结构化后写入该物料的社区经验（tip 卡片），并同步向量库。"""
    db = SessionLocal()
    try:
        return experience_core(db, material_id, user_id, content)
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
