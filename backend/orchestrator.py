"""智能体编排引擎：意图识别 → 槽位检查（必要时澄清）→ 本地/联网/通用阶梯 → LLM 综合。

交互规则见 docs/agent-workflow.md（改这里之前先改文档）：
- 槽位缺失先反问，不硬答
- 本地知识库 → 联网检索 → 通用经验 → 离线兜底，每答必标 provenance
"""
import llm
import rag
from db import Material
from services import (
    _resp,
    get_user_stats_core,
    parse_json_loose,
    recommend_bom_core,
)
from websearch import web_search

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

# 对话状态（内存，按 conv_id；重启即失效——前端表现为"再问一次就好"）
_CONV: dict[str, dict] = {}

_SELF_OWNED_OPTION = "都不是，是我自己的物料"


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
    data = parse_json_loose(raw)
    intent = (data or {}).get("intent")
    if intent in INTENT_LABELS:
        return intent
    for name, keywords in _INTENT_KEYWORDS.items():
        if any(kw in message for kw in keywords):
            return name
    return "chitchat"


# ---------- 物料定位 ----------

def _bigrams(text: str) -> set[str]:
    return {text[i : i + 2] for i in range(len(text) - 1)}

# 通用词二元组（"模块""传感器"这类词不构成定位依据，排除防误配）
_GENERIC_BIGRAMS: set[str] = set()
for _w in ["模块", "传感器", "开发板", "套装", "设备", "工具", "耗材"]:
    _GENERIC_BIGRAMS |= _bigrams(_w)


def _score_material(m: Material, message: str) -> int:
    """消息与物料的相关度：全名 > 型号 > 特征二元组。"""
    score = 0
    if m.name in message:
        score += 10
    model_token = (m.model or "").split()[0] if m.model else ""
    if model_token and model_token.lower() in message.lower():
        score += 5
    salient = (_bigrams(m.name) | _bigrams(m.model or "")) - _GENERIC_BIGRAMS
    score += sum(1 for g in salient if g in message)
    return score


def _find_target_material(db, active_borrows: list[dict], message: str):
    """定位故障物料，返回 (material|None, score, from_borrows)。

    借用清单内的匹配优先（他借了什么大概率就是问什么，特征词命中即算定位）；
    清单无匹配才扫全量目录——目录匹配只是猜测（弱匹配必须澄清确认）。
    """
    best, best_score = None, 0
    for b in active_borrows:
        m = db.get(Material, b["material_id"])
        if m is None:
            continue
        s = _score_material(m, message)
        if s > best_score:
            best, best_score = m, s
    if best is not None:
        return best, best_score, True
    best, best_score = None, 0
    for m in db.query(Material).all():
        s = _score_material(m, message)
        if s > best_score:
            best, best_score = m, s
    return best, best_score, False


# 现象具体性：命中具体现象词才算说清楚；"坏了/不行了"这类算模糊
_CONCRETE_PHENOMENA = [
    "不转", "不亮", "没反应", "没输出", "读数", "报错", "发烫", "发热", "异响", "抖",
    "冒烟", "短路", "烧", "不稳", "乱码", "连不上", "下载失败", "上传失败", "超时", "漂移", "不动",
]
_PHENOMENON_OPTIONS = ["完全不转/完全没反应", "时好时坏/抖动", "有异响", "发烫或冒烟", "读数/输出异常", "其他"]


def _has_concrete_phenomenon(message: str) -> bool:
    return any(w in message for w in _CONCRETE_PHENOMENA)


# ---------- 回答阶梯：本地 → 联网 → 通用 → 离线 ----------

def _gen(system: str, user: str, max_tokens: int = 800) -> str | None:
    return llm.chat(system, user, max_tokens=max_tokens, fallback=None)


# 本地命中阈值（IDF 重排分，已用相关/无关问题校准）：限定物料时上下文本身即强相关，阈值放低
LOCAL_HIT_THRESHOLD_OPEN = 2.5    # 全库开放检索
LOCAL_HIT_THRESHOLD_IN_MATERIAL = 1.0  # 已定位物料的物料内检索


def _ladder_answer(question: str, target, spare_text: str, names: str, steps: list) -> tuple[str, list, str]:
    """返回 (answer, references, provenance)。流程见 docs/agent-workflow.md。"""
    query_text = f"{target.name} {question}" if target else question

    # 1. 本地知识库（分数低于阈值视为未命中，防止"随便命中一张不相关卡片"）
    hits = rag.query(query_text, material_id=target.id if target else None, top_k=3)
    threshold = LOCAL_HIT_THRESHOLD_IN_MATERIAL if target else LOCAL_HIT_THRESHOLD_OPEN
    hits = [h for h in hits if h["score"] >= threshold]
    if not hits and target:
        hits = [h for h in rag.query(query_text, top_k=3) if h["score"] >= LOCAL_HIT_THRESHOLD_OPEN]
    if hits:
        steps.append({"step": "本地知识库命中", "detail": "、".join(f"《{h['title']}》" for h in hits)})
        context = "\n\n".join(f"【{h['title']}】\n{h['text']}" for h in hits)
        raw = _gen(
            "你是高校创新空间的排障/答疑专家。根据给定的知识片段回答，给出最可能原因 + 分步排查/操作清单"
            + (" + 备件路径。" if spare_text else "。")
            + "语气直接、给操作指令，250 字以内。",
            f"学生问题：{question}\n借用上下文：{names}\n{spare_text}\n知识片段：\n{context}",
        )
        refs = [{"card_id": h["card_id"], "title": h["title"], "url": None} for h in hits]
        return (raw or llm.MOCK_ANSWER, refs, "local_kb" if raw else "offline")

    # 2. 联网检索
    results = web_search(query_text)
    if results:
        steps.append({"step": "本地未收录，已联网检索", "detail": f"找到 {len(results)} 条网络资料"})
        snippets = "\n".join(f"- {r['title']}：{r['snippet']}" for r in results)
        raw = _gen(
            "你是高校创新空间的助教。根据联网检索到的资料摘要回答学生问题，给出可操作的步骤，"
            "200 字以内。资料与问题不相关就凭通用知识回答。",
            f"学生问题：{question}\n网络资料摘要：\n{snippets}",
        )
        refs = [{"card_id": None, "title": r["title"], "url": r["url"]} for r in results]
        return (raw or llm.MOCK_ANSWER, refs, "web" if raw else "offline")
    steps.append({"step": "联网检索失败", "detail": "退回通用经验回答"})

    # 3. 通用经验
    raw = _gen(
        "你是高校创新空间的助教。本地知识库和网络检索都没有这个问题的资料，"
        "请凭通用电子知识回答，开头必须声明「本地知识库未收录，以下为通用经验」。150 字以内。",
        f"学生问题：{question}",
    )
    if raw:
        return raw, [], "model"
    # 4. 离线兜底
    return llm.MOCK_ANSWER, [], "offline"


# ---------- 各意图分支 ----------

def _clarify(state: dict, intent: str, message: str, steps: list, options: list[str],
             question: str, target_id: str | None = None) -> dict:
    """进入澄清：挂起原始问题（含已定位物料），等用户下一条补充。"""
    state["pending"] = {"intent": intent, "message": message, "target_id": target_id}
    steps.append({"step": "信息不足，发起澄清", "detail": question})
    return _resp(0, "ok", {
        "intent": intent,
        "steps": steps,
        "answer": question,
        "references": [],
        "provenance": None,
        "clarify": {"question": question, "options": options},
    })


def _troubleshoot(db, user_id: str, message: str, steps: list, state: dict,
                  allow_clarify: bool, forced_target_id: str | None = None,
                  no_catalog_guess: bool = False) -> dict:
    """排障分支：确认上下文 → 槽位检查（物料+现象，不足则澄清）→ 阶梯回答。"""
    stats = get_user_stats_core(db, user_id)
    active = stats["active_borrows"] if stats else []
    names = "、".join(b["material_name"] for b in active) or "无（当前没有借用中的物料）"
    steps.append({"step": "确认借用上下文", "detail": f"你当前借用：{names}"})

    if forced_target_id:
        # 澄清后带回来的物料：直接采信，跳过定位
        target, score, from_borrows = db.get(Material, forced_target_id), 99, True
    elif no_catalog_guess:
        # 用户已明确"不是系统内的物料"：禁止目录猜测，按外部物料处理
        target, score, from_borrows = None, 0, False
    else:
        target, score, from_borrows = _find_target_material(db, active, message)

    if allow_clarify:
        # 物料槽位：借用清单内命中算定位；全目录弱匹配（<2 分）只是猜测，要确认
        material_ok = target is not None and (from_borrows or score >= 2)
        phenomenon_ok = _has_concrete_phenomenon(message)
        if not material_ok or not phenomenon_ok:
            options: list[str] = []
            parts: list[str] = []
            if not material_ok:
                candidates = [b["material_name"] for b in active]
                if target is not None and target.name not in candidates:
                    candidates.insert(0, f"{target.name}（猜的）")
                options += candidates[:4] + [_SELF_OWNED_OPTION]
                parts.append("是哪个物料")
            if not phenomenon_ok:
                if material_ok:
                    # 物料已定只缺现象：候选项给常见现象
                    options = _PHENOMENON_OPTIONS
                    parts.append("具体什么现象")
                else:
                    parts.append("什么现象（完全不转/时好时坏/异响/发烫）")
            question = "为了准确排查，先确认一下：" + "，".join(parts) + "？"
            return _clarify(state, "troubleshoot", message, steps, options, question,
                            target_id=target.id if (target and (from_borrows or score >= 2)) else None)

    if target:
        steps.append({"step": "定位故障物料", "detail": f"{target.name}（{target.id}）"})
        spare_text = (
            f"备件：{target.name} 当前可借 {target.available_quantity} 件，存放于 {target.location}，确认损坏可立即更换"
            if target.available_quantity > 0
            else f"备件：{target.name} 暂时无库存，可到 {target.location} 登记等待"
        )
        steps.append({"step": "确认备件库存", "detail": spare_text})
    else:
        steps.append({"step": "定位故障物料", "detail": "未定位到在库物料，按通用排障处理"})
        spare_text = ""

    answer, refs, provenance = _ladder_answer(message, target, spare_text, names, steps)
    return _resp(0, "ok", {
        "intent": "troubleshoot", "steps": steps,
        "answer": answer, "references": refs, "provenance": provenance, "clarify": None,
    })


def _chitchat(db, message: str, steps: list) -> dict:
    """开放式问答：无槽位检查，直接走回答阶梯。"""
    answer, refs, provenance = _ladder_answer(message, None, "", "", steps)
    return _resp(0, "ok", {
        "intent": "chitchat", "steps": steps,
        "answer": answer, "references": refs, "provenance": provenance, "clarify": None,
    })


def _recommend(db, user_id: str, message: str, steps: list) -> dict:
    res = recommend_bom_core(db, message, user_id)
    bom = res["data"]
    steps.append({"step": "生成物料方案", "detail": f"匹配到 {len(bom['materials'])} 件物料并完成库存校验"})
    # 明细交给前端内联的 BOM 卡片展示，文字部分保持简洁
    answer = f"为你生成了方案：{bom['project_guess']}。物料已校验库存，可直接一键预约："
    return _resp(0, "ok", {
        "intent": "recommend", "steps": steps, "answer": answer,
        "references": [], "provenance": "local_kb", "clarify": None, "bom": bom,
    })


def _inventory(db, message: str, steps: list) -> dict:
    found = [
        m for m in db.query(Material).all()
        if m.name in message or (m.model and m.model.split()[0] in message) or m.category in message
    ]
    if found:
        steps.append({"step": "查询库存", "detail": "、".join(m.name for m in found)})
        text = "\n".join(
            f"· {m.name}：可借 {m.available_quantity}/{m.total_quantity} 件，在 {m.location}" for m in found
        )
    else:
        steps.append({"step": "查询库存", "detail": "没听清具体物料，未命中"})
        text = "你想查哪件物料？说个名字我帮你查，比如「Arduino 还有吗」。"
    return _resp(0, "ok", {
        "intent": "inventory", "steps": steps, "answer": text,
        "references": [], "provenance": "local_kb", "clarify": None,
    })


# ---------- 编排入口 ----------

def _dispatch(db, user_id: str, message: str, steps: list, state: dict, allow_clarify: bool,
              forced_intent: str | None, forced_target_id: str | None = None,
              no_catalog_guess: bool = False) -> dict:
    intent = forced_intent or classify_intent(message)
    steps.insert(0, {"step": "意图识别", "detail": f"识别为「{INTENT_LABELS[intent]}」"})
    if intent == "troubleshoot":
        return _troubleshoot(db, user_id, message, steps, state, allow_clarify, forced_target_id, no_catalog_guess)
    if intent == "recommend":
        return _recommend(db, user_id, message, steps)
    if intent == "inventory":
        return _inventory(db, message, steps)
    return _chitchat(db, message, steps)


def agent_chat(db, user_id: str, message: str, conv_id: str = "default") -> dict:
    """编排入口。conv_id 标识对话（前端生成），用于澄清状态的挂起与恢复。"""
    state = _CONV.setdefault(conv_id, {})
    pending = state.pop("pending", None)
    if pending:
        # 本条消息是对澄清问题的回答
        if pending.get("awaiting_custom_material"):
            # 用户补充了自带物料的名称/型号：不再做任何目录猜测，直接按外部物料回答
            merged = f"{pending['message']}。用户自带物料：{message}"
            steps = [{"step": "澄清补充", "detail": f"原问题「{pending['message']}」+ 自带物料「{message}」"}]
            return _dispatch(db, user_id, merged, steps, state, allow_clarify=False,
                             forced_intent=pending["intent"], no_catalog_guess=True)
        if message == _SELF_OWNED_OPTION:
            # "都不是"只排除了系统内物料，还没问出是什么——再追问名称/型号（最后一轮澄清）
            state["pending"] = {**pending, "awaiting_custom_material": True}
            question = "好的，是你自己的物料。它叫什么名字、什么型号？（如 SG90 舵机、42 步进电机、直流减速电机）"
            steps = [{"step": "信息不足，发起澄清", "detail": "物料不在系统中，追问名称/型号"}]
            return _resp(0, "ok", {
                "intent": pending["intent"], "steps": steps, "answer": question,
                "references": [], "provenance": None,
                "clarify": {"question": question, "options": []},
            })
        # 点了候选物料或回答了现象：与原始问题合并后重走流程，不再二次澄清
        forced_target = None
        if pending.get("target_id"):
            merged = f"{pending['message']}。具体现象：{message}"
            forced_target = pending["target_id"]
        elif pending["intent"] == "troubleshoot":
            merged = f"{pending['message']}。故障物料是：{message.replace('（猜的）', '')}"
        else:
            merged = f"{pending['message']} {message}"
        steps = [{"step": "澄清补充", "detail": f"原问题「{pending['message']}」+ 补充「{message}」"}]
        return _dispatch(db, user_id, merged, steps, state, allow_clarify=False,
                         forced_intent=pending["intent"], forced_target_id=forced_target)
    return _dispatch(db, user_id, message, [], state, allow_clarify=True, forced_intent=None)
