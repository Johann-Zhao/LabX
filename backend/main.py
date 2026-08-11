"""LabX 后端 —— 阶段 0：假接口骨架。

所有接口按 API.md 契约返回写死的假数据，前端可立即对接开发；
后续按阶段逐个把假数据换成真实实现（SQLite / Chroma / LLM）。
接口契约见仓库根目录 API.md，改动契约先在群里同步。
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="LabX API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ---------- 请求体模型 ----------

class BorrowReq(BaseModel):
    user_id: str
    material_id: str
    safety_confirmed: bool = False  # 进阶级物料首次借用需勾选"我已知晓"


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


# ---------- 假数据 ----------

FAKE_MATERIALS = [
    {
        "material_id": "A-017",
        "name": "Arduino Uno 开发板",
        "model": "Uno R3",
        "category": "开发板",
        "access_level": "advanced",
        "total_quantity": 5,
        "available_quantity": 3,
        "location": "201室 A柜",
        "description": "入门首选单片机开发板，适合绝大多数创意原型项目。",
    },
    {
        "material_id": "S-003",
        "name": "DHT22 温湿度传感器",
        "model": "DHT22 / AM2302",
        "category": "传感器",
        "access_level": "basic",
        "total_quantity": 10,
        "available_quantity": 8,
        "location": "201室 B柜",
        "description": "数字温湿度传感器，单总线通信，注意数据脚需上拉。",
    },
    {
        "material_id": "M-011",
        "name": "L298N 电机驱动模块",
        "model": "L298N 双H桥",
        "category": "驱动模块",
        "access_level": "advanced",
        "total_quantity": 4,
        "available_quantity": 2,
        "location": "201室 A柜",
        "description": "直流电机/步进电机驱动，逻辑电源与电机电源需分开供电。",
    },
]

FAKE_KNOWLEDGE_CARD = {
    "card_id": "KC-S003-ERR",
    "title": "DHT22 最易错点",
    "points": [
        "数据脚必须接 4.7kΩ 上拉电阻，否则读数永远是 0",
        "通常配合面包板和杜邦线使用，你借了吗？",
        "读数异常先用示例代码自检，再怀疑硬件",
    ],
    "link": "/materials/S-003",
}


def ok(msg: str, data) -> dict:
    """统一成功返回格式，见 API.md。"""
    return {"code": 0, "msg": msg, "data": data}


# ---------- 接口 ----------

@app.get("/api/ping")
def ping():
    return {"msg": "pong"}


@app.get("/api/materials")
def list_materials(keyword: str = "", category: str = ""):
    """物料列表 + 搜索。keyword 匹配名称/型号，category 精确过滤。"""
    result = FAKE_MATERIALS
    if keyword:
        result = [m for m in result
                  if keyword.lower() in (m["name"] + m["model"]).lower()]
    if category:
        result = [m for m in result if m["category"] == category]
    return ok("ok", result)


@app.get("/api/materials/{material_id}")
def get_material(material_id: str):
    """物料详情：基础信息 + 知识卡片摘要 + 社区经验条数。"""
    for m in FAKE_MATERIALS:
        if m["material_id"] == material_id:
            detail = {
                **m,
                "knowledge_cards": [
                    {"card_id": "KC-S003-MAN", "card_type": "manual", "title": "说明书要点"},
                    {"card_id": "KC-S003-QS", "card_type": "quickstart", "title": "3 分钟上手"},
                    {"card_id": "KC-S003-ERR", "card_type": "common_errors", "title": "常见错误"},
                ],
                "tips_count": 2,
            }
            return ok("ok", detail)
    return {"code": 404, "msg": f"物料 {material_id} 不存在", "data": None}


@app.post("/api/borrow")
def borrow(req: BorrowReq):
    """借用。进阶级首次借用且未安全确认 → code 1002；专业级 → code 1003。"""
    material = next((m for m in FAKE_MATERIALS if m["material_id"] == req.material_id), None)
    if material is None:
        return {"code": 404, "msg": f"物料 {req.material_id} 不存在", "data": None}
    if material["access_level"] == "advanced" and not req.safety_confirmed:
        return {"code": 1002, "msg": "首次借用进阶级物料，请完成安全确认", "data": {
            "safety_notice": "电烙铁/驱动模块注意高温与反接，用完务必归位断电。"}}
    if material["access_level"] == "professional":
        return {"code": 1003, "msg": "专业级物料需教师审批，已提交申请", "data": None}
    return ok("借用成功", {
        "record_id": "R-1024",
        "material_id": req.material_id,
        "status": "active",
        "borrowed_at": "2026-08-11T20:30:00",
        "due_at": "2026-08-25T20:30:00",
        "knowledge_card": FAKE_KNOWLEDGE_CARD,
    })


@app.post("/api/return")
def return_material(req: ReturnReq):
    """归还。返回 AI 预填的心得草稿（阶段 3 接 LLM，现为假数据）。"""
    return ok("归还成功", {
        "record_id": req.record_id,
        "status": "returned",
        "returned_at": "2026-08-11T21:00:00",
        "experience_draft": "这次用 DHT22 测温室数据比较顺利，提醒大家：数据脚一定记得接上拉电阻，我开始忘了接，读数一直是 0。",
    })


@app.get("/api/records")
def list_records(user_id: str = ""):
    """借用流水。借用记录页使用；user_id 为空时返回全部（管理员视角）。"""
    records = [
        {
            "record_id": "R-1024",
            "user_id": user_id or "2024001",
            "material_id": "S-003",
            "material_name": "DHT22 温湿度传感器",
            "status": "active",
            "borrowed_at": "2026-08-11T20:30:00",
            "due_at": "2026-08-25T20:30:00",
            "returned_at": None,
        },
        {
            "record_id": "R-1020",
            "user_id": user_id or "2024001",
            "material_id": "A-017",
            "material_name": "Arduino Uno 开发板",
            "status": "returned",
            "borrowed_at": "2026-07-20T10:00:00",
            "due_at": "2026-08-03T10:00:00",
            "returned_at": "2026-08-01T15:20:00",
        },
    ]
    return ok("ok", records)


@app.post("/api/ask")
def ask(req: AskReq):
    """RAG 问答（现为假数据）。阶段 2 接 Chroma + LLM，并保留断网兜底。"""
    return ok("ok", {
        "answer": "DHT22 读数一直是 0，最常见的原因是数据脚没接上拉电阻。请检查：1) DATA 脚接 4.7kΩ 上拉电阻到 VCC；2) 用官方示例代码自检；3) 确认供电为 3.3-5V。",
        "references": [
            {"card_id": "KC-S003-ERR", "title": "DHT22 最易错点"},
            {"card_id": "KC-S003-QS", "title": "DHT22 3 分钟上手"},
        ],
    })


@app.post("/api/recommend_bom")
def recommend_bom(req: RecommendBomReq):
    """愿望到方案（现为假数据）。阶段 3 接 LLM，物料仅从物料目录中选择。"""
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
    """提交使用经验，返回 LLM 结构化结果（现为假数据）。"""
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
