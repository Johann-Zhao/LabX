"""LabX 后端（REST 接口层，全部为薄封装）。

借还状态机、权限、RAG 问答、BOM 生成、经验沉淀的核心逻辑在 services.py（REST 与 MCP 共用）；
编排引擎在 orchestrator.py；检索见 rag.py，LLM 封装见 llm.py。
接口契约见仓库根目录 API.md，改动契约先在群里同步。
"""
import json

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import BorrowRecord, KnowledgeCard, Material, SessionLocal, User, display_status
from services import ask_core, borrow_core, experience_core, recommend_bom_core, return_core, review_borrow_core

app = FastAPI(title="LabX API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------- 请求体模型 ----------

class BorrowReq(BaseModel):
    user_id: str
    material_id: str
    safety_confirmed: bool = False  # 进阶级首次借用需勾选"我已知晓"（阶段 3 启用）
    days: int = 30  # 借期（天），>30 需填 reason 并人工审核（API.md 第 3 节）
    reason: str = ""  # 超期借用申请理由


class ReviewReq(BaseModel):
    record_id: str
    approve: bool  # true 通过借出 / false 驳回


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


class AgentChatReq(BaseModel):
    user_id: str
    message: str
    conv_id: str = "default"  # 前端为每个对话页生成的会话 ID，用于澄清状态挂起/恢复


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
        "review_status": r.review_status,  # approved/pending/rejected
        "review_reason": r.review_reason,
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


# ---------- 知识卡片全文 ----------

@app.get("/api/cards/{card_id}")
def get_card(card_id: str, db: Session = Depends(get_db)):
    """知识卡片全文（详情页"查看全部"入口）：标题、三要点、正文 markdown、来源网址。"""
    c = db.get(KnowledgeCard, card_id)
    if c is None:
        return err(404, f"知识卡片 {card_id} 不存在")
    return ok("ok", {
        "card_id": c.id,
        "material_id": c.material_id,
        "card_type": c.card_type,
        "title": c.title,
        "points": json.loads(c.points),
        "content": c.content,
        "source": c.source,
        "helpful_count": c.helpful_count,
    })


# ---------- 借还（核心逻辑在 services.py，REST/MCP 共用） ----------

@app.post("/api/borrow")
def borrow(req: BorrowReq, db: Session = Depends(get_db)):
    """借用。进阶级首次借用需安全确认（1002），专业级需教师审批（1003）；
    借期 >30 天需填理由（否则 1006）并转人工审核（pending，不扣库存）。"""
    return borrow_core(db, req.user_id, req.material_id, req.safety_confirmed, req.days, req.reason)


@app.post("/api/borrow/review")
def review_borrow(req: ReviewReq, db: Session = Depends(get_db)):
    """超期借用审核（管理端，演示用 /docs 调用）：通过则借出并扣库存，驳回转 rejected。"""
    return review_borrow_core(db, req.record_id, req.approve)


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


# ---------- 用户 ----------

@app.get("/api/users")
def list_users(db: Session = Depends(get_db)):
    """用户列表（演示切换账号用）。"""
    return ok("ok", [{"user_id": u.id, "name": u.name} for u in db.query(User).all()])


# ---------- 智能体编排 ----------

@app.post("/api/agent/chat")
def agent_chat_endpoint(req: AgentChatReq, db: Session = Depends(get_db)):
    """智能体对话：意图识别 → 槽位检查（必要时澄清）→ 本地/联网/通用阶梯 → 综合生成。

    交互规则见 docs/agent-workflow.md；steps 为中间调用过程（演示展示用）。
    """
    from orchestrator import agent_chat
    return agent_chat(db, req.user_id, req.message, req.conv_id)


# ---------- 愿望到方案与经验沉淀（核心逻辑在 services.py） ----------

@app.post("/api/recommend_bom")
def recommend_bom(req: RecommendBomReq, db: Session = Depends(get_db)):
    """愿望到方案：LLM 从真实物料目录中选件，逐条库存校验。"""
    return recommend_bom_core(db, req.description, req.user_id)


@app.post("/api/experience")
def share_experience(req: ExperienceReq, db: Session = Depends(get_db)):
    """提交使用经验：LLM 结构化后写入 tip 卡片并同步向量库。"""
    return experience_core(db, req.material_id, req.user_id, req.content, req.record_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
