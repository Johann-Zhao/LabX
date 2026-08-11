"""业务核心逻辑：借还状态机 + RAG 问答。

main.py 的 REST 接口和 mcp_servers/ 的 MCP 工具都调用这里，
保证状态机只有一份实现（AGENTS.md 第 6 节）。
"""
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from db import BorrowRecord, KnowledgeCard, Material, User

BORROW_DAYS = 14  # 借用时长：两周（应还时间 = 借用时间 + 14 天）


def _resp(code: int, msg: str, data=None) -> dict:
    """统一响应体，与 API.md 一致。"""
    return {"code": code, "msg": msg, "data": data}


def next_record_id(db: Session) -> str:
    """记录编号 R-1001 起递增（演示规模无并发，计数即可）。"""
    return f"R-{1001 + db.query(BorrowRecord).count()}"


def push_card_dict(db: Session, material_id: str) -> dict | None:
    """借用触发的知识推送：取该物料的"常见错误"卡片（没有则取任意一张）。"""
    card = db.query(KnowledgeCard).filter(
        KnowledgeCard.material_id == material_id,
        KnowledgeCard.card_type == "common_errors",
    ).first() or db.query(KnowledgeCard).filter(
        KnowledgeCard.material_id == material_id
    ).first()
    if card is None:
        return None
    return {
        "card_id": card.id,
        "title": card.title,
        "points": json.loads(card.points),
        "link": f"/materials/{material_id}",
    }


def borrow_core(db: Session, user_id: str, material_id: str) -> dict:
    """借用状态机（见方案文档 4.2 节）。阶段 3 在此加分级权限拦截。"""
    m = db.get(Material, material_id)
    if m is None:
        return _resp(404, f"物料 {material_id} 不存在")
    if db.get(User, user_id) is None:
        return _resp(404, f"用户 {user_id} 不存在")
    # 重复借用：同一用户对该物料有未完结记录（借用中/待审批）→ 提示先归还
    existing = db.query(BorrowRecord).filter(
        BorrowRecord.user_id == user_id,
        BorrowRecord.material_id == material_id,
        BorrowRecord.status.in_(["active", "pending"]),
    ).first()
    if existing is not None:
        return _resp(1005, "你已借出该物料，请先归还", {"record_id": existing.id})
    if m.available_quantity < 1:
        return _resp(1001, "库存不足，可加入预约等待队列")

    now = datetime.now()
    record = BorrowRecord(
        id=next_record_id(db),
        user_id=user_id,
        material_id=m.id,
        quantity=1,
        status="active",
        borrowed_at=now,
        due_at=now + timedelta(days=BORROW_DAYS),
    )
    m.available_quantity -= 1
    db.add(record)
    db.commit()
    return _resp(0, "借用成功", {
        "record_id": record.id,
        "material_id": m.id,
        "status": "active",
        "borrowed_at": record.borrowed_at.isoformat(),
        "due_at": record.due_at.isoformat(),
        "knowledge_card": push_card_dict(db, m.id),
    })


def return_core(db: Session, record_id: str) -> dict:
    """归还：active/overdue → returned，库存 +1。experience_draft 由阶段 3 接入 LLM。"""
    r = db.get(BorrowRecord, record_id)
    if r is None:
        return _resp(404, f"借用记录 {record_id} 不存在")
    if r.status == "returned":
        return _resp(1004, "该记录已归还，请勿重复操作")
    if r.status == "pending":
        return _resp(1004, "该记录仍在待审批状态，无需归还")

    r.status = "returned"
    r.returned_at = datetime.now()
    m = db.get(Material, r.material_id)
    if m is not None:
        m.available_quantity += 1
    db.commit()
    return _resp(0, "归还成功", {
        "record_id": r.id,
        "status": "returned",
        "returned_at": r.returned_at.isoformat(),
        "experience_draft": None,  # 阶段 3：LLM 预填心得草稿
    })


def ask_core(question: str, material_id: str | None = None, top_k: int = 3) -> dict:
    """RAG 问答：物料内精确过滤 → 向量检索 top_k → LLM 生成（带引用）。

    LLM 不可达时 llm.chat 自动降级为兜底答案，永远返回 code 0（见 NFR2）。
    """
    import llm
    import rag

    hits = rag.query(question, material_id=material_id, top_k=top_k)
    if not hits and material_id:
        hits = rag.query(question, top_k=top_k)  # 物料内没命中 → 全库兜底
    if not hits:
        return _resp(0, "ok", {
            "answer": "知识库里还没有相关内容，可以换个问法，或联系管理员补充该物料的知识卡片。",
            "references": [],
        })

    context = "\n\n".join(f"【{h['title']}】\n{h['text']}" for h in hits)
    system = (
        "你是高校创新空间的助教 LabX。只根据给定的知识片段回答学生的问题，"
        "语气直接、具体、给操作指令；知识片段没有的内容就老实说不知道，"
        "并建议学生查看物料详情页或咨询管理员。回答控制在 150 字以内。"
    )
    user = f"知识片段：\n{context}\n\n学生问题：{question}"
    answer = llm.chat(system, user)
    return _resp(0, "ok", {
        "answer": answer,
        "references": [{"card_id": h["card_id"], "title": h["title"]} for h in hits],
    })
