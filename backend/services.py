"""业务核心逻辑：借还状态机 + 权限 + RAG 问答 + 愿望到方案 + 经验沉淀。

main.py 的 REST 接口和 mcp_servers/ 的 MCP 工具都调用这里，
保证状态机只有一份实现（AGENTS.md 第 6 节）。
"""
import json
import os
import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from db import BorrowRecord, KnowledgeCard, Material, MaterialSequence, Upload, User

DEFAULT_BORROW_DAYS = 30  # 默认借期（≤30 天免审核）
MAX_BORROW_DAYS = 180  # 借期上限（一学期）
REVIEW_THRESHOLD_DAYS = 30  # 超过该天数需填写理由 + 人工审核


def _resp(code: int, msg: str, data=None) -> dict:
    """统一响应体，与 API.md 一致。"""
    return {"code": code, "msg": msg, "data": data}


def material_to_dict(m: Material) -> dict:
    """物料基础字段序列化：REST 列表/详情与 material-mcp 共用一份。"""
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


def new_record_id() -> str:
    """记录编号 R-<uuid32>：无数据库读取、无全局计数，多进程并发也不冲突。"""
    return f"R-{uuid.uuid4().hex}"


def _begin_immediate(db: Session) -> None:
    """SQLite 短事务升级为写锁：进入事务立即取 RESERVED 锁，
    让后续"条件 UPDATE → INSERT"组合在并发下串行执行，杜绝写-写竞态窗口。
    """
    db.execute(text("BEGIN IMMEDIATE"))


def _atomic_decrement_stock(db: Session, material_id: str, quantity: int) -> bool:
    """原子扣库存：UPDATE ... WHERE available_quantity >= :qty。
    返回是否扣减成功（rowcount==1）。库存不足或物料不存在 → False。
    """
    res = db.execute(
        update(Material)
        .where(Material.id == material_id, Material.available_quantity >= quantity)
        .values(available_quantity=Material.available_quantity - quantity,
                updated_at=datetime.now())
    )
    return res.rowcount == 1


def _atomic_increment_stock(db: Session, material_id: str, quantity: int) -> bool:
    """原子回补库存：带上限保护（available + qty <= total）。"""
    res = db.execute(
        update(Material)
        .where(Material.id == material_id,
               Material.available_quantity + quantity <= Material.total_quantity)
        .values(available_quantity=Material.available_quantity + quantity,
                updated_at=datetime.now())
    )
    return res.rowcount == 1


def _next_material_seq(db: Session, prefix: str) -> int:
    """从序列表原子取物料序号：UPDATE ... SET next_seq = next_seq + 1 RETURNING。
    序列表行由 init_db 预建；不存在则按需插入（兜底）。"""
    res = db.execute(
        update(MaterialSequence)
        .where(MaterialSequence.prefix == prefix)
        .values(next_seq=MaterialSequence.next_seq + 1)
        .returning(MaterialSequence.next_seq)
    )
    row = res.first()
    if row is not None:
        return row[0] - 1  # 返回自增前的值
    # 兜底：该前缀尚无序号行（理论上 init_db 已建），从 1 开始
    db.add(MaterialSequence(prefix=prefix, next_seq=2))
    db.flush()
    return 1


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
            .filter(
                BorrowRecord.user_id == user_id,
                BorrowRecord.status.in_(["active", "returned"]),  # 只算真借过/在借，审核驳回不算
            )
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


def borrow_core(db: Session, user_id: str, material_id: str, safety_confirmed: bool = False,
                days: int = DEFAULT_BORROW_DAYS, reason: str = "", quantity: int = 1) -> dict:
    """借用状态机（见方案文档 4.2 节 + 5.6 节分级权限 + API.md 第 3 节借期分级审核）。

    并发安全设计：
    - 库存扣减用原子条件 UPDATE（WHERE available_quantity >= qty），无"读-改-写"竞态；
    - 记录编号用 UUID，无主键冲突；
    - 同一用户同一物料的未完成借用由部分唯一索引 uq_borrow_open_user_material 兜底；
    - 整个"扣库存 + 插记录"在一个短事务内，失败回滚不留半状态。
    """
    m = db.get(Material, material_id)
    if m is None:
        return _resp(404, f"物料 {material_id} 不存在")
    if db.get(User, user_id) is None:
        return _resp(404, f"用户 {user_id} 不存在")
    days = max(1, min(int(days or DEFAULT_BORROW_DAYS), MAX_BORROW_DAYS))
    try:
        quantity = max(1, min(int(quantity or 1), 10))
    except (TypeError, ValueError):
        quantity = 1
    if days > REVIEW_THRESHOLD_DAYS and not reason.strip():
        return _resp(1006, f"借用超过 {REVIEW_THRESHOLD_DAYS} 天需填写申请理由")
    # 重复借用：同一用户对该物料有未完结记录（借用中/待审核）→ 提示先归还
    # 该检查是快速路径提示；真正的并发防线是下面的部分唯一索引。
    existing = db.query(BorrowRecord).filter(
        BorrowRecord.user_id == user_id,
        BorrowRecord.material_id == material_id,
        BorrowRecord.status.in_(["active", "pending"]),
    ).first()
    if existing is not None:
        if existing.status == "pending":
            return _resp(1005, "该物料的借用申请正在审核中，请耐心等候", {"record_id": existing.id})
        return _resp(1005, "你已借出该物料，请先归还", {"record_id": existing.id})
    # 分级权限
    perm = check_permission_core(db, user_id, material_id)
    if perm["result"] == "need_approval":
        return _resp(1003, "专业级物料需教师审批，请联系实验室老师办理", {"notice": perm["notice"]})
    if perm["result"] == "need_safety_confirm" and not safety_confirmed:
        return _resp(1002, "首次借用该类物料，请完成安全确认", {"safety_notice": perm["notice"]})

    now = datetime.now()
    needs_review = days > REVIEW_THRESHOLD_DAYS
    record = BorrowRecord(
        id=new_record_id(),
        user_id=user_id,
        material_id=m.id,
        quantity=quantity,
        status="pending" if needs_review else "active",
        borrowed_at=now,
        due_at=now + timedelta(days=days),
        review_status="pending" if needs_review else "approved",
        review_reason=reason.strip() if needs_review else None,
    )
    try:
        _begin_immediate(db)
        if not needs_review:
            # 原子扣库存：库存不足时 rowcount=0，不会扣成负数
            if not _atomic_decrement_stock(db, m.id, quantity):
                db.rollback()
                fresh = db.get(Material, material_id)
                left = fresh.available_quantity if fresh else 0
                return _resp(1001, f"库存不足：需要 {quantity} 件，仅剩 {left} 件")
        db.add(record)
        db.commit()
    except IntegrityError:
        # 部分唯一索引拦截：并发下同一用户同一物料出现第二条未完成记录
        db.rollback()
        return _resp(1005, "你已借出该物料，请先归还")
    except OperationalError as e:
        db.rollback()
        if "locked" in str(e).lower():
            return _resp(1010, "系统正在处理其他库存操作，请稍后重试")
        raise
    if needs_review:
        return _resp(0, "已提交审核：超期借用申请已收到，审核通过后才算借出", {
            "record_id": record.id,
            "material_id": m.id,
            "quantity": quantity,
            "status": "pending",
            "review_status": "pending",
            "borrowed_at": record.borrowed_at.isoformat(),
            "due_at": record.due_at.isoformat(),
            "knowledge_card": None,  # 审核通过借出时才推送
        })
    return _resp(0, "借用成功", {
        "record_id": record.id,
        "material_id": m.id,
        "quantity": quantity,
        "status": "active",
        "review_status": "approved",
        "borrowed_at": record.borrowed_at.isoformat(),
        "due_at": record.due_at.isoformat(),
        "knowledge_card": push_card_dict(db, m.id),
    })


def batch_borrow_core(db: Session, user_id: str, items: list[dict], days: int = DEFAULT_BORROW_DAYS,
                      reason: str = "") -> dict:
    """批量借出（管理端代借，API.md 第 3.2 节）。

    先统一校验（用户存在 / days 截断 / days>30 无 reason → 整批 1006，不产生任何记录）；
    然后逐件调 borrow_core，管理员代借视同已当面告知安全要点（safety_confirmed=True），
    部分失败不影响其他件，results 每项如实返回 code/msg（成功带 record_id）。
    """
    if db.get(User, user_id) is None:
        return _resp(404, f"用户 {user_id} 不存在")
    days = max(1, min(int(days or DEFAULT_BORROW_DAYS), MAX_BORROW_DAYS))
    if days > REVIEW_THRESHOLD_DAYS and not (reason or "").strip():
        return _resp(1006, f"借用超过 {REVIEW_THRESHOLD_DAYS} 天需填写申请理由")
    results = []
    for it in items or []:
        if not isinstance(it, dict):
            results.append({"material_id": None, "name": "", "code": 400, "msg": "条目格式不正确", "record_id": None})
            continue
        material_id = str(it.get("material_id") or "").strip()
        if not material_id:
            results.append({"material_id": None, "name": "", "code": 400, "msg": "该条缺少 material_id", "record_id": None})
            continue
        try:
            quantity = max(1, min(int(it.get("quantity") or 1), 10))
        except (TypeError, ValueError):
            quantity = 1
        m = db.get(Material, material_id)
        r = borrow_core(db, user_id, material_id, safety_confirmed=True,
                        days=days, reason=reason, quantity=quantity)
        data = r.get("data") if isinstance(r.get("data"), dict) else {}
        results.append({
            "material_id": material_id,
            "name": m.name if m else material_id,
            "code": r["code"],
            "msg": r["msg"],
            "record_id": data.get("record_id"),
        })
    return _resp(0, "ok", {"results": results})


def review_borrow_core(db: Session, record_id: str, approve: bool) -> dict:
    """超期借用审核（管理端，演示用 /docs 调用）。

    并发安全：
    - 状态迁移用原子条件 UPDATE（WHERE status='pending'），两个管理员同时审 → 只有一个成功；
    - 通过时"状态→active + 原子扣库存"在同一事务，库存不足整体回滚，状态不被改；
    - 借期自通过时刻起算（天数=申请时的天数），补推知识卡片。
    """
    r = db.get(BorrowRecord, record_id)
    if r is None:
        return _resp(404, f"借用记录 {record_id} 不存在")
    if r.status != "pending":
        return _resp(1004, "该记录不在待审核状态，无需操作")
    qty = r.quantity or 1
    days = max(1, (r.due_at - r.borrowed_at).days)
    material_id = r.material_id
    now = datetime.now()
    try:
        _begin_immediate(db)
        if not approve:
            res = db.execute(
                update(BorrowRecord)
                .where(BorrowRecord.id == record_id, BorrowRecord.status == "pending")
                .values(status="rejected", review_status="rejected")
            )
            if res.rowcount != 1:
                db.rollback()
                return _resp(1004, "该记录不在待审核状态，无需操作")
            db.commit()
            return _resp(0, "已驳回", {"record_id": record_id, "status": "rejected", "review_status": "rejected"})
        # 通过：先原子认领 pending → active，再原子扣库存；库存不足整体回滚
        res = db.execute(
            update(BorrowRecord)
            .where(BorrowRecord.id == record_id, BorrowRecord.status == "pending")
            .values(status="active", review_status="approved",
                    borrowed_at=now, due_at=now + timedelta(days=days))
        )
        if res.rowcount != 1:
            db.rollback()
            return _resp(1004, "该记录不在待审核状态，无需操作")
        if not _atomic_decrement_stock(db, material_id, qty):
            db.rollback()
            m = db.get(Material, material_id)
            left = m.available_quantity if m else 0
            return _resp(1001, f"库存不足：需要 {qty} 件，仅剩 {left} 件，暂无法通过")
        db.commit()
    except OperationalError as e:
        db.rollback()
        if "locked" in str(e).lower():
            return _resp(1010, "系统正在处理其他库存操作，请稍后重试")
        raise
    return _resp(0, "已通过，物料借出", {
        "record_id": record_id,
        "status": "active",
        "review_status": "approved",
        "borrowed_at": now.isoformat(),
        "due_at": (now + timedelta(days=days)).isoformat(),
        "knowledge_card": push_card_dict(db, material_id),
    })


def return_core(db: Session, record_id: str) -> dict:
    """归还：仅 active（含动态判定的 overdue）→ returned，库存回补，附 AI 预填心得草稿。

    并发安全：
    - 状态认领用原子条件 UPDATE（WHERE status='active'），并发重复归还只有一个成功；
    - 库存回补带上限保护，与状态迁移同事务，失败回滚不重复加库存；
    - AI 心得草稿在事务外生成，失败不影响已成功的归还。
    """
    r = db.get(BorrowRecord, record_id)
    if r is None:
        return _resp(404, f"借用记录 {record_id} 不存在")
    if r.status == "returned":
        return _resp(1004, "该记录已归还，请勿重复操作")
    if r.status == "pending":
        return _resp(1004, "该记录仍在待审批状态，无需归还")
    if r.status != "active":
        return _resp(1004, "该记录不在借用中状态，无需归还")

    qty = r.quantity or 1
    material_id = r.material_id
    now = datetime.now()
    try:
        _begin_immediate(db)
        # 原子认领 active → returned：并发下只有一个请求能改成功
        res = db.execute(
            update(BorrowRecord)
            .where(BorrowRecord.id == record_id, BorrowRecord.status == "active")
            .values(status="returned", returned_at=now)
        )
        if res.rowcount != 1:
            db.rollback()
            return _resp(1004, "该记录不在借用中状态，无需归还")
        if not _atomic_increment_stock(db, material_id, qty):
            db.rollback()
            return _resp(1011, "库存回补失败：数量异常，请联系管理员")
        db.commit()
    except OperationalError as e:
        db.rollback()
        if "locked" in str(e).lower():
            return _resp(1010, "系统正在处理其他库存操作，请稍后重试")
        raise
    return _resp(0, "归还成功", {
        "record_id": record_id,
        "status": "returned",
        "returned_at": now.isoformat(),
        "experience_draft": experience_draft_core(db, db.get(BorrowRecord, record_id)),
    })


# ---------- 物料录入（管理端，API.md 第 1.1 节） ----------

# 分类 → 编号前缀映射（编号 = 前缀 + 该前缀现有最大序号 + 1，三位数字）
CATEGORY_PREFIX = {"开发板": "A", "传感器": "S", "驱动模块": "M", "工具": "T", "耗材": "H", "设备": "E"}


def create_material_core(db: Session, name: str, category: str, model: str = "", location: str = "201室",
                         total_quantity: int = 1, access_level: str = "basic", description: str = "") -> dict:
    """录入新物料（管理端）：分类前缀映射 + 名称去重 + 自动生成编号。

    并发安全：编号取自序列表 material_sequences（原子 UPDATE ... RETURNING），
    替代"扫描同前缀最大序号+1"；名称唯一索引兜底防并发录入同名物料。
    分类不在映射内 / 名称与现有物料重复 → 1007。
    """
    name = (name or "").strip()
    category = (category or "").strip()
    if not name or not category:
        return _resp(1007, "名称和分类不能为空")
    prefix = CATEGORY_PREFIX.get(category)
    if prefix is None:
        return _resp(1007, f"分类非法：{category}（可选：开发板/传感器/驱动模块/工具/耗材/设备）")
    exists = db.query(Material).filter(Material.name == name).first()
    if exists is not None:
        return _resp(1007, f"名称已存在：{name}（编号 {exists.id}）")
    try:
        total_quantity = max(1, min(int(total_quantity or 1), 99))
    except (TypeError, ValueError):
        total_quantity = 1
    if access_level not in ("basic", "advanced", "professional"):
        access_level = "basic"
    now = datetime.now()
    try:
        _begin_immediate(db)
        new_id = f"{prefix}-{_next_material_seq(db, prefix):03d}"
        m = Material(
            id=new_id, name=name, category=category, model=(model or "").strip(),
            location=(location or "201室").strip(), total_quantity=total_quantity,
            available_quantity=total_quantity, access_level=access_level,
            description=(description or "").strip(), created_at=now, updated_at=now,
        )
        db.add(m)
        db.commit()
    except IntegrityError:
        db.rollback()
        return _resp(1007, f"名称已存在：{name}")
    except OperationalError as e:
        db.rollback()
        if "locked" in str(e).lower():
            return _resp(1010, "系统正在处理其他库存操作，请稍后重试")
        raise
    return _resp(0, "ok", {
        "material_id": m.id, "name": m.name, "model": m.model, "category": m.category,
        "access_level": m.access_level, "total_quantity": m.total_quantity,
        "available_quantity": m.available_quantity, "location": m.location,
        "description": m.description, "knowledge_cards": [], "tips_count": 0,
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


# ---------- 愿望到方案（语义转译，方案 5.2 节 + docs/agent-workflow.md） ----------

def bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}

# 通用词二元组（"模块""传感器"这类词不构成定位依据，排除防误配）
GENERIC_BIGRAMS: set[str] = set()
for _w in ["模块", "传感器", "开发板", "套装", "设备", "工具", "耗材"]:
    GENERIC_BIGRAMS |= bigrams(_w)


def _is_salient_bigram(g: str) -> bool:
    """特征二元组过滤：含空格/符号的碎片（" R"、"B "、"-S"）和纯数字（"16"）没有区分度，不算特征。

    保留：含中文的（"电机"、"循迹"）或字母数字组合（"R3"、"4B"、"5V"）。
    """
    if any(c.isspace() for c in g):
        return False
    if any("一" <= c <= "鿿" for c in g):
        return True
    return g.isalnum() and not g.isdigit()


def score_material(m: Material, message: str) -> int:
    """消息与物料的相关度：全名 > 型号 > 特征二元组。"""
    score = 0
    if m.name in message:
        score += 10
    model_token = (m.model or "").split()[0] if m.model else ""
    if model_token and model_token.lower() in message.lower():
        score += 5
    salient = {g for g in (bigrams(m.name) | bigrams(m.model or "")) - GENERIC_BIGRAMS
               if _is_salient_bigram(g)}
    score += sum(1 for g in salient if g in message)
    return score


def recommend_bom_core(db: Session, description: str, user_id: str | None = None) -> dict:
    """自然语言项目描述 → 全链路方案 + 完整 BOM（在库/需购标记）+ 技能路径。

    LLM 按项目真实需要自由列完整物料清单（不限于目录，任何组合都能接住），
    并自行判断每件是否对应目录物料（catalog_id 由后端校验，编造无效）；
    接不住的愿望（火箭/真赛车等）幽默回应。LLM 不可用或输出异常时退回关键词匹配，接口永远可用。
    """
    import llm

    materials = db.query(Material).all()
    by_id = {m.id: m for m in materials}
    catalog = [{"material_id": m.id, "name": m.name, "category": m.category} for m in materials]

    system = (
        "你是高校创新空间的项目导师，带学生把想法做成实物。根据学生的项目想法和实验室物料目录，"
        "只输出一个 JSON 对象：\n"
        "可行项目输出：\n"
        '{"feasible": true, "project_guess": "一句话方案名", '
        '"assumption": "方案基于的默认配置假设（一句话，句尾不带标点）", '
        '"plan": ["全链路实现步骤，4-6 步，每步一句话、不带序号不含换行，覆盖结构搭建/硬件接线/代码逻辑/调试里程碑"], '
        '"bom": [{"name": "物料通用名称", "spec": "规格型号建议", "quantity": 1, "purpose": "用途，4-8字", '
        '"catalog_id": "目录中的物料ID或null"}], '
        '"skills": ["需要掌握的技能，2-4个"]}\n'
        "bom 要列全链路真实所需的全部物料（8-15 件，含主控/传感器/执行器/结构件/电源/线材耗材），"
        "不要局限于实验室目录；catalog_id 只能从给定目录里选（与目录物料确是同一类东西才填），"
        "目录没有对应物就填 null，不要编造 ID。\n"
        "明显接不住的项目（高危、需资质、成本远超学生项目，如造真赛车、火箭、光刻机）输出：\n"
        '{"feasible": false, "reply": "幽默风趣的回应（120 字以内）：先幽默点出难度，'
        '再给出一个能在创新空间落地的替代/简化项目建议"}'
    )
    user = f"实验室物料目录：\n{json.dumps(catalog, ensure_ascii=False)}\n\n学生项目：{description}"
    data = parse_json_loose(llm.chat(system, user, max_tokens=3000, fallback=None, timeout=60))

    if data and data.get("feasible") is False and data.get("reply"):
        return _resp(0, "ok", {
            "feasible": False, "reply": str(data["reply"]),
            "project_guess": "", "assumption": "", "plan": [],
            "materials": [], "skills": [], "reference_projects": [],
        })

    project_guess, assumption, plan, skills = "", "", [], []
    out_materials: list[dict] = []
    if data and isinstance(data.get("bom"), list) and data["bom"]:
        project_guess = str(data.get("project_guess") or "")
        assumption = str(data.get("assumption") or "").rstrip("。，, ")
        # plan 条目可能带序号或混入字面 \n，统一清洗成干净短句
        for s in data.get("plan", []):
            text = str(s).replace("\\n", "\n").replace("\\r", "\n")  # 字面转义序列先归一成真换行
            for piece in re.split(r"\n+", text):
                piece = re.sub(r"^\s*\d+\s*[.、．]\s*", "", piece).strip().strip("\\").strip("；; ")
                if piece:
                    plan.append(piece)
        plan = plan[:6]
        skills = [str(s) for s in data.get("skills", [])][:4]
        lab_rows: dict[str, dict] = {}  # material_id → 行（同一件目录物料合并成一行）
        for it in data["bom"][:15]:
            if not isinstance(it, dict) or not it.get("name"):
                continue
            try:
                qty = max(1, min(int(it.get("quantity") or 1), 20))
            except (TypeError, ValueError):
                qty = 1
            m = by_id.get(str(it.get("catalog_id") or ""))  # 只认目录里真实存在的 ID
            if m is not None:
                if m.id in lab_rows:  # 同一目录物料被引用多次：数量合并
                    row = lab_rows[m.id]
                    row["quantity"] = min(row["quantity"] + qty, 20)
                    purpose = str(it.get("purpose") or "")
                    if purpose and purpose not in row["purpose"]:
                        row["purpose"] += "；" + purpose
                    continue
                row = {
                    "material_id": m.id, "name": m.name, "spec": m.model or str(it.get("spec") or ""),
                    "quantity": qty, "purpose": str(it.get("purpose") or ""), "source": "lab",
                    "available_quantity": m.available_quantity,
                    "in_stock": m.available_quantity > 0,
                }
                lab_rows[m.id] = row
                out_materials.append(row)
            else:
                out_materials.append({
                    "material_id": None, "name": str(it["name"]), "spec": str(it.get("spec") or ""),
                    "quantity": qty, "purpose": str(it.get("purpose") or ""), "source": "buy",
                    "available_quantity": 0, "in_stock": False,
                })

    if not out_materials:
        # 兜底：关键词匹配（物料名/分类/描述出现在项目描述中），只列在库件、无方案步骤
        chosen = [
            m for m in materials
            if any(kw and kw in description for kw in (m.name, m.category, *(m.description or "").split("，")))
        ][:6]
        return _resp(0, "ok", {
            "feasible": True,
            "project_guess": "（离线关键词匹配方案）",
            "assumption": "", "plan": [],
            "materials": [
                {
                    "material_id": m.id, "name": m.name, "spec": m.model or "",
                    "quantity": 1, "purpose": "", "source": "lab",
                    "available_quantity": m.available_quantity,
                    "in_stock": m.available_quantity > 0,
                }
                for m in chosen
            ],
            "skills": [], "reference_projects": [],
        })

    return _resp(0, "ok", {
        "feasible": True,
        "project_guess": project_guess,
        "assumption": assumption,
        "plan": plan,
        "materials": out_materials,
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


# ---------- 用户上传资料与审核（多模态知识扩展） ----------

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
# 鼓励文案：上传即肯定，审核后帮助更多人
_UPLOAD_THANKS = "感谢分享！你的资料已收到，管理员审核通过后就会并入知识库帮助更多同学。"
_UPLOAD_REVIEW_PASS = "感谢分享！你的资料已通过审核，正式加入知识库，会帮助到更多同学。"


def new_upload_id() -> str:
    """上传编号 U-<uuid32>。"""
    return f"U-{uuid.uuid4().hex}"


def _upload_to_dict(u: Upload, user_name: str | None = None, material_name: str | None = None) -> dict:
    return {
        "upload_id": u.id,
        "user_id": u.user_id,
        "user_name": user_name or u.user_id,
        "material_id": u.material_id,
        "material_name": material_name,
        "filename": u.filename,
        "file_type": u.file_type,
        "file_size": u.file_size,
        "status": u.status,
        "review_note": u.review_note,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def upload_file_core(db: Session, user_id: str, material_id: str | None,
                     filename: str, file_content: bytes, content_type: str | None,
                     persist: bool = True) -> dict:
    """保存上传文件并解析内容，返回上传记录与鼓励文案。

    文件写入 backend/uploads/，解析后的文本存入 parsed_text（图片不存文本）。
    任何格式不支持或超大文件都会提前返回错误。
    persist=False 用于对话临时附件（purpose=chat）：只解析并返回 file_context，
    不落盘、不进资料审核队列——"问问题带的附件"不等于"向知识库投稿"。
    """
    from file_parser import parse_file

    if db.get(User, user_id) is None:
        return _resp(404, f"用户 {user_id} 不存在")
    if material_id and db.get(Material, material_id) is None:
        return _resp(404, f"物料 {material_id} 不存在")

    parsed = parse_file(file_content, filename, content_type)
    if not parsed["ok"]:
        return _resp(400, parsed["msg"])

    if not persist:
        # 对话临时附件：解析结果直接作为 file_context 返回，不产生待审记录
        file_context = {k: v for k, v in parsed.items() if k != "ok"}
        return _resp(0, "ok", {"file_context": file_context})

    upload_id = new_upload_id()
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", filename)  # 防路径注入
    file_path = os.path.join(UPLOAD_DIR, f"{upload_id}_{safe_name}")
    with open(file_path, "wb") as f:
        f.write(file_content)

    u = Upload(
        id=upload_id,
        user_id=user_id,
        material_id=material_id,
        filename=filename,
        file_path=os.path.relpath(file_path, os.path.dirname(UPLOAD_DIR)),
        file_type=parsed["type"],
        file_size=len(file_content),
        status="pending",
        parsed_text=parsed.get("text") if parsed["type"] == "text" else None,
        created_at=datetime.now(),
    )
    db.add(u)
    db.commit()
    return _resp(0, _UPLOAD_THANKS, _upload_to_dict(u))


def list_uploads_core(db: Session, status: str | None = None, user_id: str | None = None) -> dict:
    """查询上传列表：管理端可查全部，学生只能查自己的。"""
    q = db.query(Upload)
    if status:
        q = q.filter(Upload.status == status)
    if user_id:
        q = q.filter(Upload.user_id == user_id)
    uploads = q.order_by(Upload.created_at.desc()).all()
    user_names = {u.id: u.name for u in db.query(User).all()}
    material_names = {m.id: m.name for m in db.query(Material).all()}
    return _resp(0, "ok", [
        _upload_to_dict(u, user_names.get(u.user_id), material_names.get(u.material_id))
        for u in uploads
    ])


def get_upload_core(db: Session, upload_id: str) -> dict:
    """获取单个上传记录详情（含解析后的文本，管理端预览用）。"""
    u = db.get(Upload, upload_id)
    if u is None:
        return _resp(404, f"上传记录 {upload_id} 不存在")
    user_names = {u.id: u.name for u in db.query(User).all()}
    material_names = {m.id: m.name for m in db.query(Material).all()}
    data = _upload_to_dict(u, user_names.get(u.user_id), material_names.get(u.material_id))
    data["parsed_text"] = u.parsed_text
    return _resp(0, "ok", data)


def review_upload_core(db: Session, upload_id: str, approve: bool, note: str = "") -> dict:
    """管理员审核上传资料：通过则转为知识卡片（tip），驳回则标记 rejected。

    通过时：若有关联物料，生成该物料的 tip 卡片；无关联物料则生成通用 tip（material_id 为 "GENERAL"）。
    """
    import rag

    u = db.get(Upload, upload_id)
    if u is None:
        return _resp(404, f"上传记录 {upload_id} 不存在")
    if u.status != "pending":
        return _resp(400, f"该资料已审核过（当前状态：{u.status}）")

    u.review_note = note or None
    if not approve:
        u.status = "rejected"
        db.commit()
        return _resp(0, "已驳回", _upload_to_dict(u))

    # 审核通过：生成知识卡片
    u.status = "approved"
    material_id = u.material_id or "GENERAL"
    material = db.get(Material, material_id) if u.material_id else None
    material_name = material.name if material else "通用资料"

    n = db.query(KnowledgeCard).count()
    card = KnowledgeCard(
        id=f"KC-UPLOAD-{1000 + n}",
        material_id=material_id,
        card_type="tip",
        title=f"{u.filename}（{material_name}）",
        points=json.dumps([f"来源：{u.user_id} 上传分享", f"文件类型：{u.file_type}"], ensure_ascii=False),
        content=u.parsed_text or f"[图片资料] {u.filename}，请查看原文件。",
        contributor_id=u.user_id,
        helpful_count=0,
        created_at=datetime.now(),
    )
    db.add(card)
    db.commit()
    rag.add_card(card)
    return _resp(0, _UPLOAD_REVIEW_PASS, _upload_to_dict(u))
