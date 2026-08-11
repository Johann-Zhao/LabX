"""业务核心逻辑：借还状态机 + 权限 + RAG 问答 + 愿望到方案 + 经验沉淀。

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


def parse_json_loose(raw: str | None) -> dict | None:
    """从 LLM 输出里宽松提取第一个 JSON 对象（容忍前后废话和 ```json 围栏）。"""
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None


def next_record_id(db: Session) -> str:
    """记录编号 R-1001 起递增（演示规模无并发，计数即可）。"""
    return f"R-{1001 + db.query(BorrowRecord).count()}"


# ---------- 用户与权限 ----------

def get_user_stats_core(db: Session, user_id: str) -> dict | None:
    """用户借用统计与当前借用清单（编排引擎确认上下文用）。"""
    user = db.get(User, user_id)
    if user is None:
        return None
    records = db.query(BorrowRecord).filter(BorrowRecord.user_id == user_id).all()
    names = {m.id: m.name for m in db.query(Material).all()}
    active = [
        {
            "record_id": r.id,
            "material_id": r.material_id,
            "material_name": names.get(r.material_id, r.material_id),
            "borrowed_at": r.borrowed_at.isoformat(),
            "due_at": r.due_at.isoformat(),
        }
        for r in records if r.status == "active"
    ]
    return {
        "user_id": user.id,
        "name": user.name,
        "total_borrows": len(records),
        "returned_count": sum(1 for r in records if r.status == "returned"),
        "active_borrows": active,
    }


def check_permission_core(db: Session, user_id: str, material_id: str) -> dict:
    """分级借阅权限（方案 5.6 节）。

    返回 {"result": "ok" | "need_safety_confirm" | "need_approval", "notice": str}。
    - professional：一律需教师审批
    - advanced：首次借用该"类"物料需 10 秒安全确认（要点取自该物料的常见错误卡片）
    - basic：直接放行
    """
    m = db.get(Material, material_id)
    if m is None:
        return {"result": "ok", "notice": ""}
    if m.access_level == "professional":
        return {"result": "need_approval", "notice": "专业级物料需教师审批后才能借用"}
    if m.access_level == "advanced":
        # 首次借用该类别：该用户没有此类别的任何历史记录
        borrowed_categories = (
            db.query(Material.category)
            .join(BorrowRecord, BorrowRecord.material_id == Material.id)
            .filter(BorrowRecord.user_id == user_id)
            .all()
        )
        if m.category not in {c for (c,) in borrowed_categories}:
            card = db.query(KnowledgeCard).filter(
                KnowledgeCard.material_id == material_id,
                KnowledgeCard.card_type == "common_errors",
            ).first()
            points = json.loads(card.points) if card else []
            notice = "安全要点：\n" + "\n".join(f"{i + 1}. {p}" for i, p in enumerate(points)) \
                if points else "请按规范操作，注意用电与高温安全，用完务必归位。"
            return {"result": "need_safety_confirm", "notice": notice}
    return {"result": "ok", "notice": ""}


# ---------- 借还状态机 ----------

def push_card_dict(db: Session, material_id: str) -> dict | None:
    """借用触发的知识推送：该物料的"常见错误"卡片（没有则取任意一张）。

    社区闭环（方案 5.4 节）：若该物料已有社区经验，最新一条以
    "前一位同学提醒"的形式插在要点首位。
    """
    card = db.query(KnowledgeCard).filter(
        KnowledgeCard.material_id == material_id,
        KnowledgeCard.card_type == "common_errors",
    ).first() or db.query(KnowledgeCard).filter(
        KnowledgeCard.material_id == material_id
    ).first()
    if card is None:
        return None
    points = json.loads(card.points)
    latest_tip = db.query(KnowledgeCard).filter(
        KnowledgeCard.material_id == material_id,
        KnowledgeCard.card_type == "tip",
    ).order_by(KnowledgeCard.created_at.desc()).first()
    if latest_tip:
        tip_points = json.loads(latest_tip.points)
        tip_text = tip_points[0] if tip_points else (latest_tip.content or "")[:60]
        points = [f"△ 前一位同学提醒：{tip_text}"] + points[: max(0, 3 - 1)]
    return {
        "card_id": card.id,
        "title": card.title,
        "points": points[:3],
        "link": f"/materials/{material_id}",
    }


def borrow_core(db: Session, user_id: str, material_id: str, safety_confirmed: bool = False) -> dict:
    """借用状态机（见方案文档 4.2 节 + 5.6 节分级权限）。"""
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
    # 分级权限
    perm = check_permission_core(db, user_id, material_id)
    if perm["result"] == "need_approval":
        return _resp(1003, "专业级物料需教师审批，请联系实验室老师办理", {"notice": perm["notice"]})
    if perm["result"] == "need_safety_confirm" and not safety_confirmed:
        return _resp(1002, "首次借用该类物料，请完成安全确认", {"safety_notice": perm["notice"]})
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
    """归还：active/overdue → returned，库存 +1，附 AI 预填心得草稿。"""
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
        "experience_draft": experience_draft_core(db, r),
    })


# ---------- 知识问答（RAG） ----------

def ask_core(question: str, material_id: str | None = None, top_k: int = 3) -> dict:
    """RAG 问答：物料内精确过滤 → 向量检索 top_k → LLM 生成（带引用）。

    LLM 不可达时 llm.chat 自动降级为兜底答案，永远返回 code 0（见 NFR2）。
    检索分数低于阈值视为未命中（与 orchestrator 的阶梯口径一致，见 docs/agent-workflow.md）。
    """
    import llm
    import rag

    hits = rag.query(question, material_id=material_id, top_k=top_k)
    threshold = 1.0 if material_id else 2.5
    hits = [h for h in hits if h["score"] >= threshold]
    if not hits and material_id:
        hits = [h for h in rag.query(question, top_k=top_k) if h["score"] >= 2.5]  # 物料内没命中 → 全库兜底
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


# ---------- 愿望到方案（语义转译，方案 5.2 节） ----------

def recommend_bom_core(db: Session, description: str, user_id: str | None = None) -> dict:
    """自然语言项目描述 → 库存校验后的物料清单 + 技能路径。

    关键技巧（指南）：把物料目录塞进 prompt，LLM 只能从中选择，不产生幻觉物料。
    LLM 不可用或输出异常时退回关键词匹配，接口永远可用。
    """
    import llm

    materials = db.query(Material).all()
    by_id = {m.id: m for m in materials}
    catalog = [
        {"material_id": m.id, "name": m.name, "category": m.category, "description": m.description}
        for m in materials
    ]

    system = (
        "你是高校创新空间的物料专家。根据学生的项目描述，从给定物料目录中挑选所需物料。"
        "只输出一个 JSON 对象，不要输出任何其他内容：\n"
        '{"project_guess": "一句话概括项目方案", "material_ids": ["目录中存在的material_id"], '
        '"skills": ["需要掌握的技能，2-4个"]}\n'
        "规则：只能从目录里选，不要编造目录没有的物料；选 3-6 件核心物料。"
    )
    user = f"物料目录：\n{json.dumps(catalog, ensure_ascii=False)}\n\n学生项目：{description}"
    data = parse_json_loose(llm.chat(system, user, max_tokens=1500, fallback=None))

    material_ids: list[str] = []
    project_guess, skills = "", []
    if data and isinstance(data.get("material_ids"), list):
        material_ids = [mid for mid in data["material_ids"] if mid in by_id]  # 只保留真实存在的
        project_guess = str(data.get("project_guess") or "")
        skills = [str(s) for s in data.get("skills", [])][:4]

    if not material_ids:
        # 兜底：关键词匹配（物料名/分类/描述出现在项目描述中）
        material_ids = [
            m.id for m in materials
            if any(kw and kw in description for kw in (m.name, m.category, *(m.description or "").split("，")))
        ][:6]
        project_guess = project_guess or "（离线关键词匹配方案）"

    chosen = [by_id[mid] for mid in material_ids]
    return _resp(0, "ok", {
        "project_guess": project_guess,
        "materials": [
            {
                "material_id": m.id,
                "name": m.name,
                "available_quantity": m.available_quantity,
                "in_stock": m.available_quantity > 0,
            }
            for m in chosen
        ],
        "skills": [{"name": s, "link": ""} for s in skills],
        "reference_projects": [],  # 阶段 4 接入往期项目库
    })


# ---------- 归还心得与经验沉淀（方案 5.4 节） ----------

def experience_draft_core(db: Session, record: BorrowRecord) -> str:
    """AI 预填心得草稿：按物料、借用时长、该物料常见坑生成学生口吻草稿。

    LLM 不可用时退回模板拼装，保证归还流程不被打断。
    """
    import llm

    m = db.get(Material, record.material_id)
    name = m.name if m else record.material_id
    days = max(1, ((record.returned_at or datetime.now()) - record.borrowed_at).days + 1)
    card = db.query(KnowledgeCard).filter(
        KnowledgeCard.material_id == record.material_id,
        KnowledgeCard.card_type == "common_errors",
    ).first()
    points = json.loads(card.points) if card else []

    template = f"这次用{name}完成了项目，前后用了约 {days} 天。"
    if points:
        template += f"提醒下一个同学：{points[0]}。祝大家顺利！"
    raw = llm.chat(
        "你是高校创新空间的学生助教。根据物料名称、使用天数和该物料的常见坑，"
        "帮学生写一段归还心得草稿，学生口吻、真诚具体、60 字以内、只输出心得正文。",
        f"物料：{name}\n使用天数：{days} 天\n该物料常见坑：{'；'.join(points) or '无'}",
        max_tokens=300,
        fallback=None,
    )
    return raw or template


def experience_core(db: Session, material_id: str, user_id: str, content: str,
                    record_id: str | None = None) -> dict:
    """经验入库：LLM 结构化为（问题/解决方案/适用场景），写入 tip 卡片并同步向量库。"""
    import llm
    import rag

    if db.get(Material, material_id) is None:
        return _resp(404, f"物料 {material_id} 不存在")
    user = db.get(User, user_id)
    if user is None:
        return _resp(404, f"用户 {user_id} 不存在")

    raw = llm.chat(
        "你是知识整理助手。把学生的一段物料使用心得结构化为 JSON，只输出 JSON：\n"
        '{"problem": "解决了什么问题", "solution": "具体做法", "scenario": "适用场景"}\n'
        "每项一句话，忠实于原文，不要发挥。",
        f"物料：{material_id}\n心得原文：{content}",
        max_tokens=500,
        fallback=None,
    )
    structured = parse_json_loose(raw) or {"problem": "", "solution": content[:100], "scenario": ""}

    n = db.query(KnowledgeCard).count()
    card = KnowledgeCard(
        id=f"KC-TIP-{1000 + n}",
        material_id=material_id,
        card_type="tip",
        title=f"{user.name}的{material_id}心得：{structured.get('solution', '')[:20] or '使用经验'}",
        points=json.dumps([structured["solution"]] if structured.get("solution") else [], ensure_ascii=False),
        content=content,
        contributor_id=user_id,
        helpful_count=0,
        created_at=datetime.now(),
    )
    db.add(card)
    if record_id:
        record = db.get(BorrowRecord, record_id)
        if record is not None:
            record.experience_shared = True
    db.commit()
    rag.add_card(card)  # 增量进向量库，下一个借用者立刻能检索到
    return _resp(0, "经验已提交，感谢分享", {"tip_id": card.id, "structured": structured})
