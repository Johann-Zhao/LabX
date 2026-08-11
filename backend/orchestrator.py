"""智能体编排引擎：意图识别 → 调用各 MCP 能力 → LLM 综合。

阶段 3 第一版就是"意图分类 + 分支调用"（指南原话），不搞框架、不搞分布式。
排障分支是演示高潮：确认借用上下文 → 检索故障知识 → 确认备件 → 综合生成，
每一步都记入 steps 返回给前端展示（"四个 MCP Server 被动态编排"的现场证据）。
"""
import llm
import rag
from db import Material, SessionLocal
from services import (
    _resp,
    ask_core,
    get_user_stats_core,
    recommend_bom_core,
)

INTENT_LABELS = {
    "troubleshoot": "故障排查",
    "recommend": "项目求推荐",
    "inventory": "查库存",
    "chitchat": "闲聊/其他",
}

# 关键词兜底规则：LLM 意图识别失败时使用（断网演示也能分流）
_INTENT_KEYWORDS = {
    "troubleshoot": ["不转", "没反应", "不工作", "坏了", "故障", "不亮", "读数", "报错", "排查", "发烫", "烧"],
    "recommend": ["想做", "做一个", "推荐", "清单", "需要哪些", "需要什么物料", "方案"],
    "inventory": ["还有吗", "有吗", "库存", "在哪", "放在", "能借吗", "有没有"],
}


def classify_intent(message: str) -> str:
    """LLM 意图分类，输出受限 JSON；失败时退回关键词规则。"""
    raw = llm.chat(
        "你是意图分类器。把学生的消息分为四类之一：troubleshoot（设备/物料出故障求排查）、"
        "recommend（描述项目想法求物料方案）、inventory（问某物料有没有/在哪/库存）、chitchat（其他）。"
        '只输出 JSON：{"intent": "troubleshoot|recommend|inventory|chitchat"}',
        message,
        max_tokens=300,
        fallback=None,
    )
    from services import parse_json_loose

    data = parse_json_loose(raw)
    intent = (data or {}).get("intent")
    if intent in INTENT_LABELS:
        return intent
    for name, keywords in _INTENT_KEYWORDS.items():
        if any(kw in message for kw in keywords):
            return name
    return "chitchat"


def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}

# 通用词二元组（"模块""传感器"这类词不构成定位依据，排除防误配）
_GENERIC_BIGRAMS: set[str] = set()
for _w in ["模块", "传感器", "开发板", "套装", "设备", "工具", "耗材"]:
    _GENERIC_BIGRAMS |= _bigrams(_w)


def _find_target_material(db, active_borrows: list[dict], message: str):
    """从用户当前借用中定位故障物料。

    匹配依据：型号 token（如 L298N）、名称中的特征二元组（如"电机""湿度"）。
    只借了一件时默认取它；多件时取命中特征最多的那件。
    """
    if not active_borrows:
        return None
    if len(active_borrows) == 1:
        return db.get(Material, active_borrows[0]["material_id"])
    best, best_score = None, 0
    for b in active_borrows:
        m = db.get(Material, b["material_id"])
        if m is None:
            continue
        score = 0
        if m.name in message:
            score += 10
        model_token = (m.model or "").split()[0] if m.model else ""
        if model_token and model_token.lower() in message.lower():
            score += 5
        salient = (_bigrams(m.name) | _bigrams(m.model or "")) - _GENERIC_BIGRAMS
        score += sum(1 for g in salient if g in message)
        if score > best_score:
            best, best_score = m, score
    return best


def _troubleshoot(db, user_id: str, message: str, steps: list) -> dict:
    """排障分支：多能力编排的演示主线。"""
    # 1. 确认借用上下文（user-mcp 能力）
    stats = get_user_stats_core(db, user_id)
    active = stats["active_borrows"] if stats else []
    names = "、".join(b["material_name"] for b in active) or "无（当前没有借用中的物料）"
    steps.append({"step": "确认借用上下文", "detail": f"你当前借用：{names}"})

    # 2. 定位故障物料
    target = _find_target_material(db, active, message)
    if target:
        steps.append({"step": "定位故障物料", "detail": f"{target.name}（{target.id}）"})

    # 3. 检索故障知识（knowledge-mcp 能力）
    hits = rag.query(message, material_id=target.id if target else None, top_k=3)
    if not hits and target:
        hits = rag.query(message, top_k=3)
    steps.append({
        "step": "检索故障知识库",
        "detail": "命中 " + ("、".join(f"《{h['title']}》" for h in hits) if hits else "未命中") ,
    })

    # 4. 备件预案（material-mcp 能力）
    spare_text = "暂无可定位物料，未查备件"
    if target:
        fresh = db.get(Material, target.id)
        spare_text = (
            f"备件：{fresh.name} 当前可借 {fresh.available_quantity} 件，存放于 {fresh.location}，"
            "确认损坏可立即更换" if fresh.available_quantity > 0
            else f"备件：{fresh.name} 暂时无库存，可到 {fresh.location} 登记等待"
        )
    steps.append({"step": "确认备件库存", "detail": spare_text})

    # 5. LLM 综合生成
    context = "\n\n".join(f"【{h['title']}】\n{h['text']}" for h in hits)
    answer = llm.chat(
        "你是高校创新空间的排障专家。根据学生的故障描述、他的借用上下文和检索到的知识片段，给出："
        "①最可能原因（一句话）②分步排查清单（每步附预期现象，不超过 4 步）③如果都不行的备件更换路径。"
        "语气直接、给操作指令，总字数 250 字以内。",
        f"学生问题：{message}\n他借用的物料：{names}\n知识片段：\n{context or '（未检索到）'}\n{spare_text}",
        max_tokens=800,
    )
    return _resp(0, "ok", {
        "intent": "troubleshoot",
        "steps": steps,
        "answer": answer,
        "references": [{"card_id": h["card_id"], "title": h["title"]} for h in hits],
    })


def agent_chat(db, user_id: str, message: str) -> dict:
    """编排入口：意图识别 → 分支调用 → 统一返回 {intent, steps, answer, references}。"""
    steps = []
    intent = classify_intent(message)
    steps.append({"step": "意图识别", "detail": f"识别为「{INTENT_LABELS[intent]}」"})

    if intent == "troubleshoot":
        return _troubleshoot(db, user_id, message, steps)

    if intent == "recommend":
        res = recommend_bom_core(db, message, user_id)
        bom = res["data"]
        steps.append({"step": "生成物料方案", "detail": f"匹配到 {len(bom['materials'])} 件物料并完成库存校验"})
        lines = [f"项目方案：{bom['project_guess']}", "", "【推荐物料】"]
        lines += [
            f"· {m['name']}（{'有货，可借 ' + str(m['available_quantity']) + ' 件' if m['in_stock'] else '暂时缺货'}）"
            for m in bom["materials"]
        ]
        if bom["skills"]:
            lines += ["", "【需要掌握的技能】"] + [f"· {s['name']}" for s in bom["skills"]]
        lines.append("\n可到「愿望到方案」页一键预约。")
        return _resp(0, "ok", {
            "intent": intent, "steps": steps, "answer": "\n".join(lines), "references": [], "bom": bom,
        })

    if intent == "inventory":
        # 直接用问题做物料模糊搜索
        from db import Material as M
        words = [w for w in message.replace("吗", "").replace("？", "").split() if w]
        found = []
        for m in db.query(M).all():
            if m.name in message or (m.model and m.model.split()[0] in message) or m.category in message:
                found.append(m)
        if found:
            steps.append({"step": "查询库存", "detail": "、".join(m.name for m in found)})
            text = "\n".join(
                f"· {m.name}：可借 {m.available_quantity}/{m.total_quantity} 件，在 {m.location}" for m in found
            )
        else:
            steps.append({"step": "查询库存", "detail": "没听清具体物料，未命中"})
            text = "你想查哪件物料？说个名字我帮你查，比如「Arduino 还有吗」。"
        return _resp(0, "ok", {"intent": intent, "steps": steps, "answer": text, "references": []})

    # chitchat：走通用 RAG 问答
    res = ask_core(message)
    steps.append({"step": "知识库问答", "detail": f"引用 {len(res['data']['references'])} 张知识卡片"})
    return _resp(0, "ok", {
        "intent": intent, "steps": steps,
        "answer": res["data"]["answer"], "references": res["data"]["references"],
    })
