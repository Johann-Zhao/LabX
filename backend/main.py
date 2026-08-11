"""LabX 后端。

阶段 1：materials / borrow / return / records 已接真实数据库（SQLite via SQLAlchemy）。
阶段 2 进行中：借用成功返回该物料的真实知识卡片（knowledge_cards 表）；
ask / recommend_bom / experience 仍是假数据（ask 接 RAG、其余由阶段 3 接 LLM 与编排引擎）。
接口契约见仓库根目录 API.md，改动契约先在群里同步。
"""
from datetime import datetime, timedelta
import json

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import BorrowRecord, KnowledgeCard, Material, SessionLocal, User, display_status

app = FastAPI(title="LabX API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

BORROW_DAYS = 14  # 借用时长：两周（应还时间 = 借用时间 + 14 天）


# ---------- 请求体模型 ----------

class BorrowReq(BaseModel):
    user_id: str
    material_id: str
    safety_confirmed: bool = False  # 进阶级首次借用需勾选"我已知晓"（阶段 3 启用）


class ReturnReq(BaseModel):
    record_id: str


class AskReq(BaseModel):
    question: str
    material_id: str | None = None  # 在物料详情页提问时带上，限定该物料的知识上下文


class RecommendBomReq(BaseModel):
    description: str
    user_id: str | None = None


class ExperienceReq(BaseModel):
    material_id: str
    user_id: str
    content: str
    record_id: str | None = None  # 归还流程带入，便于关联借用记录


# ---------- 工具函数 ----------

def get_db():
    """FastAPI 依赖：每个请求一个数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ok(msg: str, data) -> dict:
    """统一成功返回格式，见 API.md。"""
    return {"code": 0, "msg": msg, "data": data}


def err(code: int, msg: str, data=None) -> dict:
    """统一业务错误返回格式，错误码表见 API.md 文末。"""
    return {"code": code, "msg": msg, "data": data}


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def material_dict(m: Material) -> dict:
    return {
        "material_id": m.id,
        "name": m.name,
        "model": m.model,
        "category": m.category,
        "access_level": m.access_level,
        "total_quantity": m.total_quantity,
        "available_quantity": m.available_quantity,
        "location": m.location,
        "description": m.description,
    }


def record_dict(r: BorrowRecord, material_name: str) -> dict:
    return {
        "record_id": r.id,
        "user_id": r.user_id,
        "material_id": r.material_id,
        "material_name": material_name,
        "status": display_status(r),  # overdue 由读取时动态判断
        "borrowed_at": iso(r.borrowed_at),
        "due_at": iso(r.due_at),
        "returned_at": iso(r.returned_at),
    }


def next_record_id(db: Session) -> str:
    """记录编号 R-1001 起递增（演示规模无并发，计数即可）。"""
    return f"R-{1001 + db.query(BorrowRecord).count()}"


# ---------- 联调检查 ----------

@app.get("/api/ping")
def ping():
    return {"msg": "pong"}


# ---------- 物料 ----------

@app.get("/api/materials")
def list_materials(keyword: str = "", category: str = "", db: Session = Depends(get_db)):
    """物料列表 + 搜索。keyword 匹配名称/型号，category 精确过滤。"""
    q = db.query(Material)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(Material.name.like(like) | Material.model.like(like))
    if category:
        q = q.filter(Material.category == category)
    return ok("ok", [material_dict(m) for m in q.all()])


@app.get("/api/materials/{material_id}")
def get_material(material_id: str, db: Session = Depends(get_db)):
    """物料详情：基础信息 + 知识卡片摘要 + 社区经验条数。"""
    m = db.get(Material, material_id)
    if m is None:
        return err(404, f"物料 {material_id} 不存在")
    cards = db.query(KnowledgeCard).filter(KnowledgeCard.material_id == material_id).all()
    return ok("ok", {
        **material_dict(m),
        "knowledge_cards": [
            {"card_id": c.id, "card_type": c.card_type, "title": c.title} for c in cards
        ],
        "tips_count": sum(1 for c in cards if c.card_type == "tip"),
    })


# ---------- 借还（状态机核心，见方案文档 4.2 节） ----------

@app.post("/api/borrow")
def borrow(req: BorrowReq, db: Session = Depends(get_db)):
    """借用：库存充足且无重复借用 → active，库存 -1。错误码见 API.md。

    阶段 1 不启用分级权限拦截（1002/1003 由阶段 3 实现）。
    """
    m = db.get(Material, req.material_id)
    if m is None:
        return err(404, f"物料 {req.material_id} 不存在")
    if db.get(User, req.user_id) is None:
        return err(404, f"用户 {req.user_id} 不存在")
    # 重复借用：同一用户对该物料有未完结记录（借用中/待审批）→ 提示先归还
    existing = db.query(BorrowRecord).filter(
        BorrowRecord.user_id == req.user_id,
        BorrowRecord.material_id == req.material_id,
        BorrowRecord.status.in_(["active", "pending"]),
    ).first()
    if existing is not None:
        return err(1005, "你已借出该物料，请先归还", {"record_id": existing.id})
    if m.available_quantity < 1:
        return err(1001, "库存不足，可加入预约等待队列")

    now = datetime.now()
    record = BorrowRecord(
        id=next_record_id(db),
        user_id=req.user_id,
        material_id=m.id,
        quantity=1,
        status="active",
        borrowed_at=now,
        due_at=now + timedelta(days=BORROW_DAYS),
    )
    m.available_quantity -= 1
    db.add(record)
    db.commit()
    return ok("借用成功", {
        "record_id": record.id,
        "material_id": m.id,
        "status": "active",
        "borrowed_at": iso(record.borrowed_at),
        "due_at": iso(record.due_at),
        "knowledge_card": push_card_dict(db, m.id),
    })


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


@app.post("/api/return")
def return_material(req: ReturnReq, db: Session = Depends(get_db)):
    """归还：active/overdue → returned，库存 +1。experience_draft 由阶段 3 接入 LLM。"""
    r = db.get(BorrowRecord, req.record_id)
    if r is None:
        return err(404, f"借用记录 {req.record_id} 不存在")
    if r.status == "returned":
        return err(1004, "该记录已归还，请勿重复操作")
    if r.status == "pending":
        return err(1004, "该记录仍在待审批状态，无需归还")

    r.status = "returned"
    r.returned_at = datetime.now()
    m = db.get(Material, r.material_id)
    if m is not None:
        m.available_quantity += 1
    db.commit()
    return ok("归还成功", {
        "record_id": r.id,
        "status": "returned",
        "returned_at": iso(r.returned_at),
        "experience_draft": None,  # 阶段 3：LLM 预填心得草稿
    })


@app.get("/api/records")
def list_records(user_id: str = "", db: Session = Depends(get_db)):
    """借用流水。user_id 为空时返回全部（管理员视角）。"""
    q = db.query(BorrowRecord)
    if user_id:
        q = q.filter(BorrowRecord.user_id == user_id)
    records = q.order_by(BorrowRecord.borrowed_at.desc()).all()
    names = {m.id: m.name for m in db.query(Material).all()}
    return ok("ok", [record_dict(r, names.get(r.material_id, r.material_id)) for r in records])


# ---------- 以下仍是假数据（阶段 2 / 阶段 3 替换为真实实现） ----------

@app.post("/api/ask")
def ask(req: AskReq):
    """RAG 问答（假数据）。阶段 2 接 Chroma + LLM，并保留断网兜底。"""
    return ok("ok", {
        "answer": "DHT22 读数一直是 0，最常见的原因是数据脚没接上拉电阻。请检查：1) DATA 脚接 4.7kΩ 上拉电阻到 VCC；2) 用官方示例代码自检；3) 确认供电为 3.3-5V。",
        "references": [
            {"card_id": "KC-S003-ERR", "title": "DHT22 最易错点"},
            {"card_id": "KC-S003-QS", "title": "DHT22 3 分钟上手"},
        ],
    })


@app.post("/api/recommend_bom")
def recommend_bom(req: RecommendBomReq):
    """愿望到方案（假数据）。阶段 3 接 LLM，物料仅从物料目录中选择。"""
    return ok("ok", {
        "project_guess": "土壤湿度监测 + 水泵控制的自动浇花装置",
        "materials": [
            {"material_id": "A-017", "name": "Arduino Uno 开发板", "available_quantity": 3, "in_stock": True},
            {"material_id": "S-003", "name": "DHT22 温湿度传感器", "available_quantity": 8, "in_stock": True},
            {"material_id": "M-011", "name": "L298N 电机驱动模块", "available_quantity": 2, "in_stock": True},
            {"material_id": "P-002", "name": "5V 微型水泵", "available_quantity": 0, "in_stock": False},
        ],
        "skills": [
            {"name": "Arduino 基础编程", "link": "/materials/A-017"},
            {"name": "继电器控制原理", "link": "/materials/M-011"},
        ],
        "reference_projects": [
            {"project_id": "P-2025-06", "title": "张XX的自动浇花系统（2025年6月）"},
            {"project_id": "P-2025-03", "title": "李XX的智能花盆（2025年3月）"},
        ],
    })


@app.post("/api/experience")
def share_experience(req: ExperienceReq):
    """提交使用经验（假数据）。阶段 3 接 LLM 结构化入库。"""
    return ok("经验已提交，感谢分享", {
        "tip_id": "TIP-0042",
        "structured": {
            "problem": "DHT22 读数一直是 0",
            "solution": "数据脚接 4.7kΩ 上拉电阻到 VCC",
            "scenario": "DHT22 首次接线、温湿度数据采集项目",
        },
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
