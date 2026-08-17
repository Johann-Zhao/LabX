"""material-mcp：物料管理 MCP Server。

FastMCP 薄封装，业务逻辑全部复用 services.py / db.py（与 REST 接口同一份实现）。
运行：python mcp_servers/material_server.py（stdio 传输，供编排引擎/评委检查调用）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from db import BorrowRecord, KnowledgeCard, Material, display_status, session_scope
from services import borrow_core, material_to_dict, return_core

mcp = FastMCP("material-mcp")


@mcp.tool()
def search_materials(query: str = "", category: str = "") -> list[dict]:
    """模糊搜索物料，返回匹配列表及库存状态。query 匹配名称/型号，category 精确过滤分类。"""
    with session_scope() as db:
        q = db.query(Material)
        if query:
            like = f"%{query}%"
            q = q.filter(Material.name.like(like) | Material.model.like(like))
        if category:
            q = q.filter(Material.category == category)
        return [material_to_dict(m) for m in q.all()]


@mcp.tool()
def get_material_detail(material_id: str) -> dict:
    """获取物料完整信息，包括知识卡片列表和社区经验条数。"""
    with session_scope() as db:
        m = db.get(Material, material_id)
        if m is None:
            return {"error": f"物料 {material_id} 不存在"}
        cards = db.query(KnowledgeCard).filter(KnowledgeCard.material_id == material_id).all()
        return {
            **material_to_dict(m),
            "knowledge_cards": [
                {"card_id": c.id, "card_type": c.card_type, "title": c.title} for c in cards
            ],
            "tips_count": sum(1 for c in cards if c.card_type == "tip"),
        }


@mcp.tool()
def borrow_material(user_id: str, material_id: str) -> dict:
    """执行借用操作，返回借用记录和推送的知识卡片。code 非 0 表示失败（见 msg）。"""
    with session_scope() as db:
        return borrow_core(db, user_id, material_id)


@mcp.tool()
def return_material(record_id: str) -> dict:
    """执行归还操作，库存 +1。code 非 0 表示失败（见 msg）。"""
    with session_scope() as db:
        return return_core(db, record_id)


@mcp.tool()
def check_inventory_alerts() -> dict:
    """检查库存预警：低库存物料（可借 ≤1）与逾期未还记录。"""
    from datetime import datetime

    with session_scope() as db:
        low_stock = [
            {"material_id": m.id, "name": m.name, "available_quantity": m.available_quantity}
            for m in db.query(Material).filter(Material.available_quantity <= 1).all()
        ]
        overdue = []
        for r in db.query(BorrowRecord).filter(BorrowRecord.status == "active").all():
            if display_status(r) == "overdue":
                overdue.append({
                    "record_id": r.id, "user_id": r.user_id,
                    "material_id": r.material_id, "due_at": r.due_at.isoformat(),
                })
        return {"low_stock": low_stock, "overdue": overdue, "checked_at": datetime.now().isoformat()}


if __name__ == "__main__":
    mcp.run()
