"""智能体编排引擎：意图识别 → 槽位检查（必要时澄清）→ 本地/联网/通用阶梯 → LLM 综合。

交互规则见 docs/agent-workflow.md（改这里之前先改文档）：
- 槽位缺失先反问，不硬答
- 本地知识库 → 联网检索 → 通用经验 → 离线兜底，每答必标 provenance
"""
import re

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
_ESCAPE_OPTION = "不用问了，直接回答"  # 逃生项：用户有权跳过澄清


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


def _resolve_material_id(db, name: str, active_borrows: list[dict]) -> str | None:
    """把澄清回答（选项文本或自由输入）解析为系统内物料 ID；解析不出返回 None。"""
    for b in active_borrows:
        if b["material_name"] == name:
            return b["material_id"]
    m = db.query(Material).filter(Material.name == name).first()
    if m:
        return m.id
    # 自由输入：按特征词模糊匹配，分数过低不算命中
    best, best_score = None, 0
    for m in db.query(Material).all():
        s = _score_material(m, name)
        if s > best_score:
            best, best_score = m, s
    return best.id if best and best_score >= 2 else None


# ---------- 回答阶梯：本地 → 联网 → 通用 → 离线 ----------

def _gen(system: str, user: str, max_tokens: int = 800) -> str | None:
    return llm.chat(system, user, max_tokens=max_tokens, fallback=None)


# 本地命中阈值（IDF 重排分，已用相关/无关问题校准）：限定物料时上下文本身即强相关，阈值放低
LOCAL_HIT_THRESHOLD_OPEN = 2.5    # 全库开放检索
LOCAL_HIT_THRESHOLD_IN_MATERIAL = 1.0  # 已定位物料的物料内检索


def _ladder_answer(question: str, target, spare_text: str, names: str, steps: list,
                   custom_material: str | None = None) -> tuple[str, list, str]:
    """返回 (answer, references, provenance)。流程见 docs/agent-workflow.md。"""
    query_text = f"{target.name} {question}" if target else question

    # 1. 本地知识库（分数低于阈值视为未命中，防止"随便命中一张不相关卡片"）
    hits = rag.query(query_text, material_id=target.id if target else None, top_k=3)
    threshold = LOCAL_HIT_THRESHOLD_IN_MATERIAL if target else LOCAL_HIT_THRESHOLD_OPEN
    hits = [h for h in hits if h["score"] >= threshold]
    if not hits and target:
        hits = [h for h in rag.query(query_text, top_k=3) if h["score"] >= LOCAL_HIT_THRESHOLD_OPEN]
    if hits:
        # 引用卫生：只保留"与最高分同物料"或"分数接近最高分（≥60%）"的，防止无关卡片混入参考列表
        top_score = hits[0]["score"]
        top_material = hits[0].get("material_id")
        hits = [h for h in hits if h.get("material_id") == top_material or h["score"] >= top_score * 0.6]
        steps.append({"step": "本地知识库命中", "detail": "、".join(f"《{h['title']}》" for h in hits)})
        context = "\n\n".join(f"【{h['title']}】\n{h['text']}" for h in hits)
        # 用户自带物料但本地只有相关物料的资料：必须披露假设，不能假装本地收录了该物料
        disclosure = (
            f"注意：学生的物料「{custom_material}」本地没有专属资料，检索到的是相关物料的资料。"
            "回答开头必须声明这个假设（如「本地没有它的专属资料，以下按最相关的方案排查」），"
            "结尾提示学生：如果实际驱动/接线不同，告诉我具体型号我再细查。"
            if custom_material else ""
        )
        raw = _gen(
            "你是高校创新空间的排障/答疑专家。根据给定的知识片段回答，给出最可能原因 + 分步排查/操作清单"
            + (" + 备件路径。" if spare_text else "。")
            + "语气直接、给操作指令，250 字以内。" + disclosure,
            f"学生问题：{question}\n借用上下文：{names}\n{spare_text}\n知识片段：\n{context}",
        )
        refs = [{"card_id": h["card_id"], "title": h["title"], "url": None} for h in hits]
        return (raw or llm.MOCK_ANSWER, refs, "local_kb" if raw else "offline")

    # 2. 联网检索（优先 DeepSeek 原生 web_search，失败退回 DuckDuckGo）
    raw = llm.chat_with_search(
        "你是高校创新空间的助教。基于联网搜索到的资料回答学生问题，给出可操作的步骤，200 字以内。",
        f"学生问题：{question}",
    )
    if raw:
        steps.append({"step": "本地未收录，已联网检索", "detail": "DeepSeek 原生联网搜索"})
        urls = re.findall(r"https?://[^\s\)\]>\"，。]+", raw)
        refs = [{"card_id": None, "title": u.split("/")[2] if "/" in u else u, "url": u} for u in urls[:3]]
        return raw, refs, "web"
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

def _clarify(state: dict, intent: str, message: str, slots: dict, awaiting: str,
             steps: list, options: list[str], question: str) -> dict:
    """挂起当前槽位进度，就下一个缺失槽位发问（每轮只问一个）。"""
    state["pending"] = {"intent": intent, "message": message, "slots": slots, "awaiting": awaiting}
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
                  allow_clarify: bool, slots: dict | None = None) -> dict:
    """排障分支：槽位（物料/现象）逐轮澄清，问清为止 → 阶梯回答。"""
    stats = get_user_stats_core(db, user_id)
    active = stats["active_borrows"] if stats else []
    names = "、".join(b["material_name"] for b in active) or "无（当前没有借用中的物料）"
    steps.append({"step": "确认借用上下文", "detail": f"你当前借用：{names}"})

    if slots is None:
        # 首次进入：从消息里自动识别两个槽位
        slots = {"material_id": None, "custom_material": None, "phenomenon": None, "guess_id": None}
        target, score, from_borrows = _find_target_material(db, active, message)
        if target is not None and (from_borrows or score >= 2):
            slots["material_id"] = target.id
        elif target is not None:
            slots["guess_id"] = target.id  # 全目录弱匹配，仅作猜测候选
        if _has_concrete_phenomenon(message):
            slots["phenomenon"] = message

    if allow_clarify:
        if not slots.get("material_id") and not slots.get("custom_material"):
            options = [b["material_name"] for b in active]
            guess_id = slots.get("guess_id")
            if guess_id:
                g = db.get(Material, guess_id)
                if g and g.name not in options:
                    options.insert(0, f"{g.name}（猜的）")
            options += [_SELF_OWNED_OPTION, _ESCAPE_OPTION]
            return _clarify(state, "troubleshoot", message, slots, "material", steps, options,
                            "为了准确排查，先确认一下：是哪个物料？")
        if not slots.get("phenomenon"):
            return _clarify(state, "troubleshoot", message, slots, "phenomenon", steps,
                            _PHENOMENON_OPTIONS + [_ESCAPE_OPTION],
                            "明白。具体是什么现象？")

    # ---- 槽位齐备（或用户选择直接回答）：组织最终问题并作答 ----
    target = db.get(Material, slots["material_id"]) if slots.get("material_id") else None
    question = message
    if slots.get("custom_material"):
        question += f"。用户自带物料：{slots['custom_material']}"
    if slots.get("phenomenon") and slots["phenomenon"] != message:
        question += f"。具体现象：{slots['phenomenon']}"

    if target:
        steps.append({"step": "定位故障物料", "detail": f"{target.name}（{target.id}）"})
        spare_text = (
            f"备件：{target.name} 当前可借 {target.available_quantity} 件，存放于 {target.location}，确认损坏可立即更换"
            if target.available_quantity > 0
            else f"备件：{target.name} 暂时无库存，可到 {target.location} 登记等待"
        )
        steps.append({"step": "确认备件库存", "detail": spare_text})
    elif slots.get("custom_material"):
        steps.append({"step": "定位故障物料", "detail": f"用户自带物料「{slots['custom_material']}」（不在目录），按外部物料处理"})
        spare_text = ""
    else:
        steps.append({"step": "定位故障物料", "detail": "未定位到物料，按通用排障处理"})
        spare_text = ""

    answer, refs, provenance = _ladder_answer(question, target, spare_text, names, steps,
                                              custom_material=slots.get("custom_material"))
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
              forced_intent: str | None, slots: dict | None = None) -> dict:
    intent = forced_intent or classify_intent(message)
    steps.insert(0, {"step": "意图识别", "detail": f"识别为「{INTENT_LABELS[intent]}」"})
    if intent == "troubleshoot":
        return _troubleshoot(db, user_id, message, steps, state, allow_clarify, slots)
    if intent == "recommend":
        return _recommend(db, user_id, message, steps)
    if intent == "inventory":
        return _inventory(db, message, steps)
    return _chitchat(db, message, steps)


def agent_chat(db, user_id: str, message: str, conv_id: str = "default") -> dict:
    """编排入口。conv_id 标识对话（前端生成），用于澄清槽位的挂起与恢复。

    澄清是逐槽位多轮的：每轮只问一个缺失槽位，直到物料+现象都清楚
    （或用户点"不用问了，直接回答"）。规则见 docs/agent-workflow.md。
    """
    state = _CONV.setdefault(conv_id, {})
    pending = state.pop("pending", None)
    if pending:
        slots = pending.get("slots") or {}
        original = pending["message"]
        awaiting = pending.get("awaiting")

        # 逃生项：用户选择跳过澄清，按已有信息直接回答
        if message == _ESCAPE_OPTION:
            steps = [{"step": "用户选择直接回答", "detail": "按当前已知信息处理"}]
            return _dispatch(db, user_id, original, steps, state,
                             allow_clarify=False, forced_intent=pending["intent"], slots=slots)

        steps = [{"step": "澄清补充", "detail": f"原问题「{original}」+ 补充「{message}」"}]
        if awaiting == "material":
            if message == _SELF_OWNED_OPTION:
                # "都不是"只是排除了系统内物料，必须再追问名称/型号
                return _clarify(state, pending["intent"], original, slots, "custom_material",
                                steps, [_ESCAPE_OPTION],
                                "好的，是你自己的物料。它叫什么名字、什么型号？（如 SG90 舵机、42 步进电机、直流减速电机）")
            name = message.replace("（猜的）", "")
            active = (get_user_stats_core(db, user_id) or {}).get("active_borrows", [])
            mid = _resolve_material_id(db, name, active)
            if mid:
                slots["material_id"] = mid
            else:
                # 自由输入且目录里也没有 → 视为自带物料
                slots["custom_material"] = name
                slots.pop("guess_id", None)
        elif awaiting == "custom_material":
            slots["custom_material"] = message
            slots.pop("guess_id", None)
        elif awaiting == "phenomenon":
            slots["phenomenon"] = message
        # 槽位推进后重入流程：还有缺失槽位会继续问，齐了自然回答
        return _dispatch(db, user_id, original, steps, state,
                         allow_clarify=True, forced_intent=pending["intent"], slots=slots)
    return _dispatch(db, user_id, message, [], state, allow_clarify=True, forced_intent=None)
