"""LabX 后端（REST 接口层，全部为薄封装）。

借还状态机与 RAG 问答的核心逻辑在 services.py（REST 与 MCP 共用一份实现）；
检索见 rag.py，LLM 封装见 llm.py。
当前 ask / borrow / return / records / materials 为真实实现；
recommend_bom / experience 仍是假数据（阶段 3 接 LLM 与编排引擎）。
接口契约见仓库根目录 API.md，改动契约先在群里同步。
"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import BorrowRecord, KnowledgeCard, Material, SessionLocal, display_status
from services import ask_core, borrow_core, return_core

app = FastAPI(title="LabX API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


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


def iso(dt) -> str | None:
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


# ---------- 借还（核心逻辑在 services.py，REST/MCP 共用） ----------

@app.post("/api/borrow")
def borrow(req: BorrowReq, db: Session = Depends(get_db)):
    """借用。阶段 1 不启用分级权限拦截（1002/1003 由阶段 3 实现）。"""
    return borrow_core(db, req.user_id, req.material_id)


@app.post("/api/return")
def return_material(req: ReturnReq, db: Session = Depends(get_db)):
    """归还。"""
    return return_core(db, req.record_id)


@app.get("/api/records")
def list_records(user_id: str = "", db: Session = Depends(get_db)):
    """借用流水。user_id 为空时返回全部（管理员视角）。"""
    q = db.query(BorrowRecord)
    if user_id:
        q = q.filter(BorrowRecord.user_id == user_id)
    records = q.order_by(BorrowRecord.borrowed_at.desc()).all()
    names = {m.id: m.name for m in db.query(Material).all()}
    return ok("ok", [record_dict(r, names.get(r.material_id, r.material_id)) for r in records])


# ---------- 知识问答（RAG，核心逻辑在 services.py） ----------

@app.post("/api/ask")
def ask(req: AskReq, db: Session = Depends(get_db)):
    return ask_core(req.question, req.material_id)


# ---------- 以下仍是假数据（阶段 3 替换为真实实现） ----------

@app.post("/api/recommend_bom")
def recommend_bom(req: RecommendBomReq):
    """愿望到方案（假数据）。阶段 3 接 LLM，物料仅从物料目录中选择。"""
    return ok("ok", {
        "project_guess": "土壤湿度监测 + 水泵控制的自动浇花装置",
        "materials": [
            {"material_id": "A-017", "name": "Arduino Uno 开发板", "available_quantity": 3, "in_stock": True},
            {"material_id": "S-007", "name": "土壤湿度传感器", "available_quantity": 6, "in_stock": True},
            {"material_id": "E-001", "name": "5V 微型水泵", "available_quantity": 3, "in_stock": True},
            {"material_id": "M-013", "name": "单路继电器模块", "available_quantity": 6, "in_stock": True},
        ],
        "skills": [
            {"name": "Arduino 基础编程", "link": "/materials/A-017"},
            {"name": "继电器控制原理", "link": "/materials/M-013"},
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
