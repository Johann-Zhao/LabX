"""knowledge-mcp：知识服务 MCP Server。

FastMCP 薄封装，RAG 问答复用 services.ask_core（Chroma 检索 + LLM 生成）。
运行：python mcp_servers/knowledge_server.py（stdio 传输，供编排引擎/评委检查调用）。
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from db import KnowledgeCard, SessionLocal
from services import ask_core

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
    """提交使用经验，写入该物料的社区经验（tip 卡片）。阶段 3 会加 LLM 结构化提炼。"""
    db = SessionLocal()
    try:
        n = db.query(KnowledgeCard).count()
        card = KnowledgeCard(
            id=f"KC-TIP-{1000 + n}",
            material_id=material_id,
            card_type="tip",
            title=f"{user_id} 的使用经验",
            points="[]",
            content=content,
            contributor_id=user_id,
            helpful_count=0,
            created_at=datetime.now(),
        )
        db.add(card)
        db.commit()
        return {"code": 0, "msg": "经验已提交，感谢分享", "tip_id": card.id}
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
