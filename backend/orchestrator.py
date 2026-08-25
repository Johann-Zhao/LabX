"""智能体编排引擎：意图识别 → 槽位检查（必要时澄清）→ 本地/联网/通用阶梯 → LLM 综合。

交互规则见 docs/agent-workflow.md（改这里之前先改文档）：
- 槽位缺失先反问，不硬答
- 本地知识库 → 联网检索 → 通用经验 → 离线兜底，每答必标 provenance
"""
import re
import time

import llm
import rag
from db import Material
from services import (
    _resp,
    get_user_stats_core,
    parse_json_loose,
    recommend_bom_core,
    score_material,
)
from websearch import web_search

INTENT_LABELS = {
    "troubleshoot": "故障排查",
    "explore": "物料求用法",
    "recommend": "项目求推荐",
    "inventory": "查库存",
    "chitchat": "闲聊/其他",
    "contribute": "投稿资料",
    "file": "附件问答",
}

# 关键词兜底规则：LLM 意图识别失败时使用（断网演示也能分流）
_INTENT_KEYWORDS = {
    "troubleshoot": ["不转", "没反应", "不工作", "坏了", "故障", "不亮", "读数", "报错", "排查", "发烫", "烧"],
    "explore": ["怎么用", "能做什么", "如何上手", "不知道该怎么用", "不知道咋用", "能用来", "玩法", "上手"],
    "recommend": ["想做", "做一个", "想造", "想搞", "做个", "推荐", "清单", "需要哪些", "需要什么物料", "方案"],
    "inventory": ["还有吗", "有吗", "库存", "在哪", "放在", "能借吗", "有没有"],
}

# 对话状态（内存，按 conv_id；重启即失效——前端表现为"再问一次就好"）
_CONV: dict[str, dict] = {}

_SELF_OWNED_OPTION = "都不是，是我自己的物料"
_ESCAPE_OPTION = "不用问了，直接回答"  # 逃生项：用户有权跳过澄清
_OTHER_PHENOMENON_OPTION = "其他"  # 现象候选项兜底：只表示"不在列表里"，不等于现象已知


# 泛称词：不是具体物料，提取结果命中这些时视为未提取（"我的电机不转" ≠ 已告知物料）
_GENERIC_MENTIONS = {
    "电机", "板子", "开发板", "传感器", "模块", "物料", "东西", "套件", "套装", "设备", "工具",
    "这个", "那个", "它", "这块", "那台", "这板子", "那板子", "这个板子", "那个板子", "这物料", "那物料",
}

# 指代/接续词：短消息命中且上一轮刚聊过某件物料 → 视为跟进该物料（跨轮次上下文）
_FOLLOWUP_WORDS = ("它", "这个", "那个", "这块", "那台", "这", "那", "怎么接", "接线", "还能干嘛",
                  "还能做什么", "怎么烧录", "怎么连", "引脚", "多少钱", "哪里借")

# 投稿意图（对话内上传资料给知识库）：明确的投稿动词，或"上传+资料/文档类名词"组合
# 注意排除排障场景的"代码上传失败"——单靠"上传"两个字不算投稿
_CONTRIBUTE_WORDS = ("投稿", "分享给知识库", "放到知识库", "发到知识库", "存入知识库", "上传到知识库", "贡献资料")
_CONTRIBUTE_NOUNS = ("资料", "文档", "手册", "参考", "笔记", "教程", "datasheet", "说明书",
                     "数据库", "知识库", "社区")  # "那上传到你的数据库里吧" 也算


def _is_contribute(message: str) -> bool:
    """判断消息是否表达"把资料投稿给知识库"的意图（关键词级，带附件时触发，省一次分类调用）。"""
    if any(w in message for w in _CONTRIBUTE_WORDS):
        return True
    return "上传" in message and any(w in message for w in _CONTRIBUTE_NOUNS)

# 会话状态最多保留 200 个 conv（内存演示规模，防长期运行越积越多）
_MAX_CONV_STATES = 200


def _clean_material_mention(value) -> str | None:
    """把 LLM 提取的物料提及清洗成可用的名称/型号。

    去掉"我的/这个/那块"这类前缀；整串只剩泛称或代词时视为未提取。
    """
    if value is None:
        return None
    mention = str(value).strip()
    if not mention or len(mention) > 30:
        return None
    mention = re.sub(r"^(我的|我手上|我手里|这个|那个|这块|那台|这|那|一个|一台|一块)", "", mention)
    mention = mention.strip("的。，, ？?！!")
    if not mention or mention in _GENERIC_MENTIONS:
        return None
    # 只含指代词/方位词，不含真实名称（如"这板子""那个"）也视为未提取
    if all(ch in "这那它个块台物料东西" for ch in mention):
        return None
    return mention


def classify_intent(message: str) -> tuple[str, str | None]:
    """LLM 意图分类 + 具体物料提取，返回 (intent, material_mention)。

    material_mention：消息中明确提到的具体物料名称/型号（RV1126B、SG90 舵机、42 步进电机）；
    泛称（电机/板子/传感器）或没提 → None。LLM 失败时退回关键词规则（无提取）。
    """
    raw = llm.chat(
        "你是意图分类器。把学生的消息分为五类之一：troubleshoot（设备/物料出故障求排查）、"
        "explore（手里有物料但不知道怎么用/能做什么/求上手指导）、"
        "recommend（描述想做/想造的项目或东西，求物料方案，如「我想做自动浇花」「我想造一台火箭」都算）、"
        "inventory（问某物料有没有/在哪/库存）、chitchat（打招呼、与物料/项目无关的其他问题）。"
        "同时提取消息里明确提到的具体物料名称/型号（如 RV1126B、SG90 舵机、42 步进电机）；"
        "只是泛称（电机/板子/传感器这类）或没提就填 null。"
        '只输出 JSON：{"intent": "troubleshoot|explore|recommend|inventory|chitchat", "material": "名称型号或null"}',
        message,
        max_tokens=300,
        fallback=None,
    )
    data = parse_json_loose(raw) or {}
    mention = _clean_material_mention(data.get("material"))
    intent = data.get("intent")
    if intent in INTENT_LABELS:
        return intent, mention
    for name, keywords in _INTENT_KEYWORDS.items():
        if any(kw in message for kw in keywords):
            return name, mention
    return "chitchat", mention


# ---------- 物料定位 ----------
# 相关度评分 score_material 与二元组工具在 services.py（BOM 匹配与排障定位共用一份实现）


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
        s = score_material(m, message)
        if s > best_score:
            best, best_score = m, s
    if best is not None:
        return best, best_score, True
    best, best_score = None, 0
    for m in db.query(Material).all():
        s = score_material(m, message)
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
        s = score_material(m, name)
        if s > best_score:
            best, best_score = m, s
    return best.id if best and best_score >= 2 else None


# ---------- 槽位解析公共逻辑（排障/求用法共用，消除重复分支） ----------

def _initial_material_slots(db, active_borrows: list[dict], message: str, mention: str | None,
                            with_phenomenon: bool = False) -> dict:
    """首次进入时解析物料槽位：借用清单优先 → 明确型号 → 目录弱匹配仅作猜测。"""
    slots: dict = {}
    target, score, from_borrows = _find_target_material(db, active_borrows, message)
    if target is not None and (from_borrows or score >= 2):
        slots["material_id"] = target.id
    elif mention:
        # 消息里已带具体型号且目录无此物料 → 直接按自带物料处理，不再问"是哪个物料"
        slots["custom_material"] = mention
    elif target is not None:
        slots["guess_id"] = target.id  # 全目录弱匹配，仅作猜测候选
    if with_phenomenon:
        slots["phenomenon"] = message if _has_concrete_phenomenon(message) else None
    return slots


def _material_clarify(state: dict, intent: str, message: str, slots: dict, steps: list,
                      db, active_borrows: list[dict], question: str) -> dict:
    """物料槽位缺失时发起澄清；候选 = 借用清单 + 目录猜测（猜的）+ 自有物料 + 逃生项。"""
    options = [b["material_name"] for b in active_borrows]
    guess_id = slots.get("guess_id")
    if guess_id:
        g = db.get(Material, guess_id)
        if g and g.name not in options:
            options.insert(0, f"{g.name}（猜的）")
    options += [_SELF_OWNED_OPTION, _ESCAPE_OPTION]
    return _clarify(state, intent, message, slots, "material", steps, options, question)


def _remember_material(state: dict, intent: str, target, custom_material: str | None) -> None:
    """记下本轮定位到的物料，供下一轮"它/这个/怎么接线"这类指代跟进使用。"""
    if target is not None:
        state["last"] = {"intent": intent, "material_id": target.id,
                         "material_name": target.name, "custom_material": None}
    elif custom_material:
        state["last"] = {"intent": intent, "material_id": None,
                         "material_name": custom_material, "custom_material": custom_material}
    state["last_ts"] = time.time()


def _followup_slots(state: dict, message: str) -> dict | None:
    """短指代消息沿用上一轮物料上下文；不含指代词则返回 None（不强行接续）。"""
    last = state.get("last")
    if not last or len(message.strip()) > 20:
        return None
    if not any(w in message for w in _FOLLOWUP_WORDS):
        return None
    # 消息里出现目录物料具体特征时不要硬接上一轮（可能是新话题）
    if message.strip() in _GENERIC_MENTIONS:
        return None
    slots = {}
    if last.get("material_id"):
        slots["material_id"] = last["material_id"]
    if last.get("custom_material"):
        slots["custom_material"] = last["custom_material"]
    if last.get("intent") == "troubleshoot" and _has_concrete_phenomenon(message):
        slots["phenomenon"] = message
    return slots or None


# ---------- 回答阶梯：本地 → 联网 → 通用 → 离线 ----------

def _gen(system: str, user: str, max_tokens: int = 800) -> str | None:
    return llm.chat(system, user, max_tokens=max_tokens, fallback=None)


# 本地命中阈值（IDF 重排分，已用相关/无关问题校准）：限定物料时上下文本身即强相关，阈值放低
LOCAL_HIT_THRESHOLD_OPEN = 2.5    # 全库开放检索
LOCAL_HIT_THRESHOLD_IN_MATERIAL = 1.0  # 已定位物料的物料内检索

# 统一回答格式：本地知识与联网检索的输出结构必须一致（见 docs/agent-workflow.md）
_ANSWER_FORMAT = (
    "输出格式（严格遵守，本地与联网回答格式一致）：\n"
    "①最可能原因（一句话）\n"
    "②分步排查/操作清单（每步附预期现象，不超过 4 步）\n"
    "③补充路径（备件位置/深入学习入口，没有可省略）\n"
)

# explore（物料求用法）专用：导师角色 + 求用法回答格式（见 docs/agent-workflow.md）
_EXPLORE_ROLE = (
    "你是高校创新空间的项目导师，学生手里有一件物料但不知道怎么用，"
    "根据给定资料回答，语气直接、可操作，250 字以内。"
)
_EXPLORE_FORMAT = (
    "输出格式（严格遵守，本地与联网回答格式一致）：\n"
    "①它是什么（一句话定位：核心能力/关键参数）\n"
    "②能做什么（2-4 个适合学生科创的用法/项目点子，每点一句话）\n"
    "③上手第一步（具体到操作：上电/接线/烧录/跑通哪个示例）\n"
    "④深入学习入口（官方文档/教程名称或网址）\n"
)

# 带附件提问专用：文件本身就是问题主体，跳过意图分类与澄清（见 docs/agent-workflow.md）
_FILE_ROLE = (
    "你是高校创新空间的助教，擅长识别电子元器件/物料（图片里的型号丝印要读出来），"
    "也能阅读理解学生上传的文档。围绕学生的问题直接回答，语气友好、可操作，250 字以内。"
)
_FILE_FORMAT = (
    "输出格式：若学生问\"这是什么/是什么物料\"，按下面结构回答：\n"
    "①这是什么（名称/型号，图中有丝印或标题要读出来）\n"
    "②能做什么（关键用途/参数，一两句）\n"
    "③上手第一步或深入学习入口（一句）\n"
    "若学生的问题是其他具体问题，直接围绕问题回答，不必套上面的结构。\n"
)


def _web_refs(raw: str) -> list[dict]:
    """从联网回答里提取引用：优先 markdown 链接，其次裸 URL。"""
    refs: list[dict] = []
    seen: set[str] = set()
    for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", raw):
        if url not in seen:
            seen.add(url)
            refs.append({"card_id": None, "title": title.strip() or url.split("/")[2], "url": url})
    for url in re.findall(r"https?://[^\s\)\]>\"，。]+", raw):
        if url not in seen:
            seen.add(url)
            refs.append({"card_id": None, "title": url.split("/")[2] if "/" in url else url, "url": url})
    return refs[:3]


def _noop_status(text: str) -> None:
    """on_status 的默认实现：不做事（非流式调用无需任何改动）。"""


def _ladder_answer(question: str, target, spare_text: str, names: str, steps: list,
                   custom_material: str | None = None, role: str | None = None,
                   answer_format: str | None = None, search_query: str | None = None,
                   on_status=None, file_context: dict | None = None) -> tuple[str, list, str]:
    """返回 (answer, references, provenance)。流程见 docs/agent-workflow.md：

    本地只在"强相关"（型号对应 + 原因对应）时使用；自带物料跳过本地直接联网。
    role / answer_format 可定制回答角色与输出结构（explore 用，默认排障专家）；
    search_query 指定检索词（默认按"物料名 + 问题"自动拼，explore 用用途导向词）。
    on_status 为可选的流式状态回调（每个真实动作前调用，诚实报告执行过程）。
    file_context 为可选的多模态文件上下文，图片走 vision 模型，文本注入 prompt。
    """
    on_status = on_status or _noop_status
    system_role = role or "你是高校创新空间的排障/答疑专家。只根据给定的知识片段回答，语气直接、给操作指令，250 字以内。"
    fmt = answer_format or _ANSWER_FORMAT
    if search_query:
        query_text = search_query
    elif target is not None:
        query_text = f"{target.name} {question}"
    elif custom_material:
        query_text = f"{custom_material} {question}"
    else:
        query_text = question
    # 备用检索词不宜太长：DuckDuckGo 对整段问题检索效果差，压到 80 字以内
    search_text = re.sub(r"\s+", " ", query_text).strip()[:80]

    # 多模态：图片直接走 vision 模型（不检索本地/联网，图片本身就是上下文）
    if file_context and file_context.get("type") == "image":
        on_status("正在识别图片内容…")
        image_prompt = f"学生上传了一张图片，问题是：{question}\n请分析图片内容并回答学生问题。"
        raw = llm.chat_with_image(
            system_role + "\n" + fmt,
            image_prompt,
            file_context.get("base64", ""),
            file_context.get("mime", "image/jpeg"),
            max_tokens=3000,  # vision-exp 推理链烧输出预算，给足（同 chat_with_search 的经验）
            fallback=None,
        )
        if raw:
            steps.append({"step": "图片识别", "detail": f"已识别上传图片：{file_context.get('filename', '未命名')}"})
            return raw, [], "model"
        steps.append({"step": "图片识别失败", "detail": "退回通用经验回答"})

    # 多模态：文本文件内容注入 prompt（本地检索时把文件内容也作为上下文）
    file_text = ""
    if file_context and file_context.get("type") == "text":
        file_text = f"\n\n【用户上传的文件内容：{file_context.get('filename', '未命名')}】\n{file_context.get('text', '')[:1500]}"
        question = question + file_text

    # 1. 本地知识库：仅当"强相关"时使用。
    #    目录内物料按物料内阈值检索；自带物料（目录外）也检索全库——
    #    社区投稿可能正好收录了该型号（rag 的型号词守卫保证命中必须含该型号，不会假命中）。
    hits = []
    if custom_material:
        on_status("正在检索本地知识库（含社区投稿）…")
        hits = rag.query(query_text, top_k=3)
        hits = [h for h in hits if h["score"] >= LOCAL_HIT_THRESHOLD_OPEN]
        if not hits:
            steps.append({"step": "自带物料，本地无对应资料", "detail": "跳过本地，直接联网检索"})
    else:
        on_status("正在检索本地知识库…")
        hits = rag.query(query_text, material_id=target.id if target else None, top_k=3)
        threshold = LOCAL_HIT_THRESHOLD_IN_MATERIAL if target else LOCAL_HIT_THRESHOLD_OPEN
        hits = [h for h in hits if h["score"] >= threshold]
    if hits:
        # 引用卫生：只保留"与最高分同物料"或"分数接近最高分（≥60%）"的，防止无关卡片混入参考列表
        on_status("本地命中，正在整理回答…")
        top_score = hits[0]["score"]
        top_material = hits[0].get("material_id")
        hits = [h for h in hits if h.get("material_id") == top_material or h["score"] >= top_score * 0.6]
        steps.append({"step": "本地知识库命中", "detail": "、".join(f"《{h['title']}》" for h in hits)})
        context = "\n\n".join(f"【{h['title']}】\n{h['text']}" for h in hits)
        raw = _gen(
            system_role + "\n" + fmt,
            f"学生问题：{question}\n借用上下文：{names}\n{spare_text}\n知识片段：\n{context}",
        )
        refs = [{"card_id": h["card_id"], "title": h["title"], "url": None} for h in hits]
        if raw:
            return raw, refs, "local_kb"
        # 本地命中但 LLM 不可用：直接摘录卡片要点（比通用兜底有用得多）
        excerpt = "（离线模式：AI 暂时不可用，以下摘录自本地资料）\n" + "\n".join(
            f"《{h['title']}》{h['text'][:120]}…" for h in hits[:2]
        )
        return excerpt, refs, "offline"

    # 2. 联网检索（优先 DeepSeek 原生 web_search，失败退回 DuckDuckGo；均要求优先官方资料）
    on_status("本地未收录，正在联网检索（官方资料优先）…")
    raw = llm.chat_with_search(
        "你是高校创新空间的助教。基于联网搜索到的资料回答学生问题，"
        "优先采用官方资料（厂商文档、数据手册、官方教程）的内容，250 字以内。\n" + fmt,
        f"学生问题：{question}",
        max_tokens=3000,  # 推理链+搜索循环很烧输出预算，1024 会把正文截断
    )
    if raw:
        steps.append({"step": "本地未收录，已联网检索", "detail": "DeepSeek 原生联网搜索（官方资料优先）"})
        refs = _web_refs(raw)
        return raw, refs, "web"
    on_status("正在用备用渠道检索…")
    results = web_search(search_text)
    if results:
        steps.append({"step": "本地未收录，已联网检索", "detail": f"找到 {len(results)} 条网络资料（官方域名优先）"})
        snippets = "\n".join(f"- {r['title']}：{r['snippet']}" for r in results)
        raw = _gen(
            "你是高校创新空间的助教。根据联网检索到的资料摘要回答学生问题，"
            "优先采用官方资料（厂商文档、数据手册、官方教程）的内容；资料与问题不相关就凭通用知识回答。"
            "250 字以内。\n" + fmt,
            f"学生问题：{question}\n网络资料摘要：\n{snippets}",
        )
        refs = [{"card_id": None, "title": r["title"], "url": r["url"]} for r in results]
        if raw:
            return raw, refs, "web"
        # 检索到资料但 LLM 不可用：摘录资料摘要
        excerpt = "（离线模式：AI 暂时不可用，以下摘录自网络资料）\n" + "\n".join(
            f"· {r['title']}：{r['snippet'][:100]}" for r in results
        )
        return excerpt, refs, "offline"
    steps.append({"step": "联网检索失败", "detail": "退回通用经验回答"})

    # 3. 通用经验
    on_status("联网也没找到，正在凭通用经验回答…")
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
                  allow_clarify: bool, slots: dict | None = None,
                  mention: str | None = None, on_status=None, file_context: dict | None = None) -> dict:
    """排障分支：槽位（物料/现象）逐轮澄清，问清为止 → 阶梯回答。"""
    on_status = on_status or _noop_status
    stats = get_user_stats_core(db, user_id)
    active = stats["active_borrows"] if stats else []
    names = "、".join(b["material_name"] for b in active) or "无（当前没有借用中的物料）"
    on_status(f"已确认你的借用清单：{names}" if active else "你当前没有借用中的物料")
    steps.append({"step": "确认借用上下文", "detail": f"你当前借用：{names}"})

    if slots is None:
        slots = _initial_material_slots(db, active, message, mention, with_phenomenon=True)

    if allow_clarify:
        if not slots.get("material_id") and not slots.get("custom_material"):
            return _material_clarify(state, "troubleshoot", message, slots, steps, db, active,
                                     "为了准确排查，先确认一下：是哪个物料？")
        if not slots.get("phenomenon"):
            return _clarify(state, "troubleshoot", message, slots, "phenomenon", steps,
                            _PHENOMENON_OPTIONS + [_ESCAPE_OPTION],
                            "明白。具体是什么现象？")

    # ---- 槽位齐备（或用户选择直接回答）：组织最终问题并作答 ----
    target = db.get(Material, slots["material_id"]) if slots.get("material_id") else None
    custom_material = slots.get("custom_material")
    question = message
    if custom_material:
        question += f"。用户自带物料：{custom_material}"
    if slots.get("phenomenon") and slots["phenomenon"] != message:
        question += f"。具体现象：{slots['phenomenon']}"

    # 诚实披露信息缺口：选了"直接回答"但槽位不全时，回答必须声明假设范围
    if not target and not custom_material:
        question += ("。注意：学生没有确认具体物料和现象，请给出通用排查方向，"
                     "并在开头说明「因为还没确认具体物料，以下按常见情况排查」。")
    elif not slots.get("phenomenon"):
        question += ("。注意：学生没有描述具体现象，请按该物料最常见故障排查，"
                     "并在开头说明「还没描述具体现象，以下按常见故障排查」。")

    if target:
        steps.append({"step": "定位故障物料", "detail": f"{target.name}（{target.id}）"})
        spare_text = (
            f"备件：{target.name} 当前可借 {target.available_quantity} 件，存放于 {target.location}，确认损坏可立即更换"
            if target.available_quantity > 0
            else f"备件：{target.name} 暂时无库存，可到 {target.location} 登记等待"
        )
        steps.append({"step": "确认备件库存", "detail": spare_text})
        _remember_material(state, "troubleshoot", target, None)
    elif custom_material:
        steps.append({"step": "定位故障物料", "detail": f"用户自带物料「{custom_material}」（不在目录），按外部物料处理"})
        spare_text = ""
        _remember_material(state, "troubleshoot", None, custom_material)
    else:
        steps.append({"step": "定位故障物料", "detail": "未定位到物料，按通用排障处理"})
        spare_text = ""

    search_query = f"{custom_material} 故障 排查 解决办法" if custom_material else None
    answer, refs, provenance = _ladder_answer(question, target, spare_text, names, steps,
                                              custom_material=custom_material,
                                              search_query=search_query,
                                              on_status=on_status, file_context=file_context)
    return _resp(0, "ok", {
        "intent": "troubleshoot", "steps": steps,
        "answer": answer, "references": refs, "provenance": provenance, "clarify": None,
    })


def _explore(db, user_id: str, message: str, steps: list, state: dict,
             allow_clarify: bool, slots: dict | None = None,
             mention: str | None = None, on_status=None, file_context: dict | None = None) -> dict:
    """物料求用法分支：槽位只要"物料"（不要现象——物料没坏，只是不知道能做什么/怎么上手）。

    目录内物料：本地 → 联网阶梯（explore 格式）；自带物料：跳过本地直连联网，
    并把实验室目录物料名列表给 LLM，要求配套建议优先提目录内的（见 docs/agent-workflow.md）。
    """
    on_status = on_status or _noop_status
    stats = get_user_stats_core(db, user_id)
    active = stats["active_borrows"] if stats else []
    names = "、".join(b["material_name"] for b in active) or "无（当前没有借用中的物料）"
    on_status(f"已确认你的借用清单：{names}" if active else "你当前没有借用中的物料")
    steps.append({"step": "确认借用上下文", "detail": f"你当前借用：{names}"})

    if slots is None:
        slots = _initial_material_slots(db, active, message, mention)

    if allow_clarify and not slots.get("material_id") and not slots.get("custom_material"):
        return _material_clarify(state, "explore", message, slots, steps, db, active,
                                 "想给你讲讲用法，先确认一下：是哪个物料？")

    # ---- 槽位齐备（或用户选择直接回答）：组织问题并作答 ----
    target = db.get(Material, slots["material_id"]) if slots.get("material_id") else None
    custom_material = slots.get("custom_material")
    question = message
    if custom_material:
        question += f"。用户自带物料：{custom_material}"

    if target:
        steps.append({"step": "定位物料", "detail": f"{target.name}（{target.id}）"})
        question += (f"。物料信息：{target.name}，型号 {target.model or '未知'}。"
                     f"{target.description or ''}".strip())
        search_query = f"{target.name} 入门教程 应用场景"
        _remember_material(state, "explore", target, None)
    elif custom_material:
        steps.append({"step": "定位物料",
                      "detail": f"用户自带物料「{custom_material}」（不在目录），按外部物料处理"})
        catalog_names = "、".join(m.name for m in db.query(Material).all())
        question += (f"\n实验室物料目录：{catalog_names}\n"
                     "如果某些用法需要搭配其他物料，优先提实验室现有的（确实配套才提，用目录里的准确名字）。")
        search_query = f"{custom_material} 开发板 入门教程 应用场景"
        _remember_material(state, "explore", None, custom_material)
    else:
        # 逃生项但没定位到物料：不做开放检索（会随机命中某件物料的卡片，答非所问）
        if active:
            steps.append({"step": "定位物料", "detail": "没指明是哪件，按你借用的物料逐个简介"})
            on_status("正在整理你借用物料的用法…")
            notes = []
            for b in active:
                m = db.get(Material, b["material_id"])
                if m:
                    notes.append(f"{m.name}：{m.description or m.category}")
            raw = _gen(
                "你是高校创新空间的项目导师。学生手里有物料但没说清是哪件。根据他当前借用的物料清单，"
                "逐个用一两句话说清它能做什么、怎么上手，最后提示：说出具体是哪一件可以再细讲。200 字以内。",
                f"学生问题：{message}\n他当前借用：\n" + "\n".join(notes),
            )
        else:
            steps.append({"step": "定位物料", "detail": "没指明是哪件，按通用介绍回答"})
            raw = _gen(
                "你是高校创新空间的项目导师。学生手里有物料但没说是什么。通用介绍常见科创物料"
                "（单片机开发板/传感器/驱动模块）各自能做什么、怎么上手，并引导他说出具体名称型号。200 字以内。",
                f"学生问题：{message}",
            )
        return _resp(0, "ok", {
            "intent": "explore", "steps": steps,
            "answer": raw or llm.MOCK_ANSWER, "references": [],
            "provenance": "model" if raw else "offline", "clarify": None,
        })

    answer, refs, provenance = _ladder_answer(
        question, target, "", names, steps,
        custom_material=custom_material,
        role=_EXPLORE_ROLE, answer_format=_EXPLORE_FORMAT,
        search_query=search_query, on_status=on_status, file_context=file_context,
    )
    # 目录内物料且可借：后端拼一句"可借引导"（不靠 LLM）
    if target and target.available_quantity > 0:
        answer += (f"\n\n这件实验室就有：可借 {target.available_quantity} 件，在 {target.location}，"
                   "看完教程想动手直接来借。")
    return _resp(0, "ok", {
        "intent": "explore", "steps": steps,
        "answer": answer, "references": refs, "provenance": provenance, "clarify": None,
    })


# 通用问答的回答格式（不要排障报告格式）
_CHITCHAT_ROLE = "你是高校创新空间的助教，回答学生的通用问题，直接、简短，200 字以内。"
_CHITCHAT_FORMAT = "输出格式：先用一句话直接回答问题，再给 2-4 条要点或建议（不要①最可能原因②排查清单的排障报告格式）。\n"

# 纯打招呼与自我介绍：直接回应，不走检索阶梯（"你好"也联网搜索又慢又怪）
_GREETINGS = ("你好", "您好", "在吗", "在么", "hi", "hello", "嗨", "谢谢", "早上好", "下午好", "晚上好")
_SELF_INTRO = ("你是谁", "你能做什么", "你会什么", "介绍一下自己", "你能干嘛", "你会干嘛", "介绍一下你")
_GREETING_ANSWER = (
    "你好呀！我是 LabX 智能助手。可以跟我说这几类事："
    "①想做项目（如「我想做自动浇花装置」）→ 我出全链路方案并一键预约物料；"
    "②物料出故障（如「我的电机不转」）→ 我逐步排查；"
    "③手里有物料不知道怎么用（如「这块板子能做什么」）→ 我讲用法；"
    "④查库存（如「Arduino 还有吗」）。"
    "除了这些，你也可以把我当学习搭子，问各种课程、技术和通用问题。"
)


def _chitchat(db, message: str, steps: list, on_status=None, file_context: dict | None = None) -> dict:
    """开放式问答：无槽位检查。

    纯打招呼/自我介绍直接固定回应；其余问题走本地→联网→通用阶梯，
    使用通用问答格式（不套排障报告），因此任何非标准化问题都能接住。
    """
    text = message.strip().lower()
    short = len(message.strip()) <= 12
    if short and (any(g in text for g in _GREETINGS) or any(g in text for g in _SELF_INTRO)):
        steps.append({"step": "闲聊", "detail": "打招呼/自我介绍，直接回应（不检索）"})
        return _resp(0, "ok", {
            "intent": "chitchat", "steps": steps,
            "answer": _GREETING_ANSWER, "references": [], "provenance": None, "clarify": None,
        })
    answer, refs, provenance = _ladder_answer(
        message, None, "", "", steps,
        role=_CHITCHAT_ROLE, answer_format=_CHITCHAT_FORMAT, on_status=on_status,
        file_context=file_context,
    )
    return _resp(0, "ok", {
        "intent": "chitchat", "steps": steps,
        "answer": answer, "references": refs, "provenance": provenance, "clarify": None,
    })


def _file_answer(db, message: str, steps: list, on_status, file_context: dict) -> dict:
    """带附件的提问：文件本身就是问题主体，跳过意图识别与槽位澄清，直接按文件内容回答。

    图片走 vision 模型直答；文本内容注入问题后走本地→联网→通用阶梯
    （_ladder_answer 内部处理），不套排障格式。
    回答后若资料是知识库未覆盖的文本类内容，附上投稿邀请（upload_offer），用户可选。
    """
    steps.insert(0, {"step": "多模态输入",
                     "detail": f"附件「{file_context.get('filename', '未命名')}」即问题主体，直接解析回答"})
    answer, refs, provenance = _ladder_answer(
        message, None, "", "", steps,
        role=_FILE_ROLE, answer_format=_FILE_FORMAT, on_status=on_status,
        file_context=file_context,
    )
    data = {
        "intent": "file", "steps": steps,
        "answer": answer, "references": refs, "provenance": provenance, "clarify": None,
    }
    offer = _maybe_upload_offer(file_context)
    if offer:
        data["upload_offer"] = offer
        steps.append({"step": "知识库未收录这份资料", "detail": "已向用户发出投稿邀请（可选）"})
    return _resp(0, "ok", data)


def _maybe_upload_offer(file_context: dict) -> dict | None:
    """文本类附件且本地知识库未覆盖时返回邀稿信息；已覆盖/图片/太短则不打扰。

    图片不走文本索引无法判重，不主动邀稿（用户仍可主动说"上传这份资料"投稿）。
    """
    if file_context.get("type") != "text":
        return None
    text = (file_context.get("text") or "").strip()
    if len(text) < 50:
        return None  # 太短没有投稿价值
    hits = rag.query(text[:300], top_k=1)
    if hits and hits[0]["score"] >= LOCAL_HIT_THRESHOLD_OPEN:
        return None  # 本地已有覆盖，不重复收录
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", file_context.get("filename", "")).strip()
    return {"filename": file_context.get("filename", "未命名"), "material_label": stem or None}


def _contribute(db, user_id: str, message: str, steps: list, on_status, file_context: dict) -> dict:
    """对话内投稿：带附件表达"上传/投稿/分享"意图 → 提炼后转入资料审核队列（管理员终审）。

    物料可以是目录外的：目录匹配不上时记 material_label（如 RV1126B），
    审核通过后生成通用知识卡片，同样可被检索。
    """
    import services

    steps.insert(0, {"step": "意图识别", "detail": "识别为「投稿资料」"})
    on_status("正在提炼资料要点并提交审核…")
    # 借意图分类器提取消息里的具体型号（RV1126B 等），尝试关联目录内物料
    _, mention = classify_intent(message)
    material_id, material_label, material_name = None, None, None
    if mention:
        m = db.query(Material).filter(Material.name.contains(mention)).first()
        if m:
            material_id, material_name = m.id, m.name
        else:
            material_label = mention
    if not material_id and not material_label:
        # 没提物料名：用文件名主干兜底，管理员审核时再判断
        material_label = re.sub(r"\.[A-Za-z0-9]+$", "", file_context.get("filename", "")).strip() or None

    res = services.persist_parsed_upload(db, user_id, file_context, material_id, material_label)
    if res["code"] != 0:
        return _resp(res["code"], res["msg"], {
            "intent": "contribute", "steps": steps,
            "answer": f"投稿失败：{res['msg']}", "references": [], "provenance": None, "clarify": None,
        })
    where = (f"已关联物料「{material_name}」" if material_id
             else f"这是目录外物料「{material_label}」，审核通过后会作为通用资料收录" if material_label
             else "暂未关联物料")
    steps.append({"step": "资料已提炼并转交审核", "detail": where})
    answer = (f"收到你的分享！我已把《{file_context.get('filename', '资料')}》提炼成要点卡片，"
              f"提交给管理员审核，{where}。审核通过后全社区同学都能检索到它——"
              f"感谢你的贡献，知识库因你更厚一层。")
    return _resp(0, "ok", {
        "intent": "contribute", "steps": steps, "answer": answer,
        "references": [], "provenance": None, "clarify": None,
    })


def _recommend(db, user_id: str, message: str, steps: list, on_status=None) -> dict:
    on_status = on_status or _noop_status
    on_status("正在生成全链路方案与物料清单…")
    res = recommend_bom_core(db, message, user_id)
    bom = res["data"]
    # 接不住的愿望（火箭/真赛车等）：幽默回应 + 替代建议，不出 BOM 卡片
    if not bom.get("feasible", True):
        steps.append({"step": "生成物料方案", "detail": "项目超出创新空间能力，给出幽默回应与替代建议"})
        return _resp(0, "ok", {
            "intent": "recommend", "steps": steps, "answer": bom["reply"],
            "references": [], "provenance": "model", "clarify": None, "bom": None,
        })
    lab_n = sum(1 for m in bom["materials"] if m["source"] == "lab")
    buy_n = len(bom["materials"]) - lab_n
    steps.append({"step": "生成物料方案",
                  "detail": f"全链路方案 {len(bom['plan'])} 步；清单 {len(bom['materials'])} 件：在库 {lab_n}、需自购 {buy_n}"})
    # 方案步骤放气泡正文（全链路是回答主体），物料明细交给前端 BOM 卡片
    answer = f"为你生成了方案：{bom['project_guess']}"
    if bom.get("assumption"):
        answer += f"\n（默认配置：{bom['assumption']}，不符就告诉我调整）"
    if bom.get("plan"):
        answer += "\n实现路线：\n" + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(bom["plan"]))
    answer += f"\n物料清单见下方卡片：在库 {lab_n} 件可一键预约，需自购 {buy_n} 件已标出。"
    return _resp(0, "ok", {
        "intent": "recommend", "steps": steps, "answer": answer,
        "references": [], "provenance": "local_kb", "clarify": None, "bom": bom,
    })


def _inventory(db, message: str, steps: list, state: dict | None = None) -> dict:
    # 用特征二元组评分（"Arduino 还有吗" 能命中 "Arduino Uno 开发板"），全名包含/型号词也已含在评分里
    found = [m for m in db.query(Material).all() if score_material(m, message) >= 2]
    if found:
        steps.append({"step": "查询库存", "detail": "、".join(m.name for m in found)})
        text = chr(10).join(
            f"· {m.name}：可借 {m.available_quantity}/{m.total_quantity} 件，在 {m.location}" for m in found
        )
        if state is not None and len(found) == 1:
            _remember_material(state, "inventory", found[0], None)
    else:
        steps.append({"step": "查询库存", "detail": "没听清具体物料，未命中"})
        text = "你想查哪件物料？说个名字我帮你查，比如「Arduino 还有吗」。"
    return _resp(0, "ok", {
        "intent": "inventory", "steps": steps, "answer": text,
        "references": [], "provenance": "local_kb", "clarify": None,
    })


# ---------- 编排入口 ----------

def _dispatch(db, user_id: str, message: str, steps: list, state: dict, allow_clarify: bool,
              forced_intent: str | None, slots: dict | None = None,
              mention: str | None = None, on_status=None, file_context: dict | None = None) -> dict:
    on_status = on_status or _noop_status
    if forced_intent:
        intent = forced_intent  # 澄清重入：意图已知，不再识别
    else:
        on_status("正在识别意图…")
        intent, mention = classify_intent(message)
    steps.insert(0, {"step": "意图识别", "detail": f"识别为「{INTENT_LABELS[intent]}」"})
    if intent == "troubleshoot":
        return _troubleshoot(db, user_id, message, steps, state, allow_clarify, slots,
                             mention=mention, on_status=on_status, file_context=file_context)
    if intent == "explore":
        return _explore(db, user_id, message, steps, state, allow_clarify, slots,
                        mention=mention, on_status=on_status, file_context=file_context)
    if intent == "recommend":
        return _recommend(db, user_id, message, steps, on_status=on_status)
    if intent == "inventory":
        return _inventory(db, message, steps, state)
    return _chitchat(db, message, steps, on_status=on_status, file_context=file_context)


def agent_chat(db, user_id: str, message: str, conv_id: str = "default", on_status=None,
               file_context: dict | None = None) -> dict:
    """编排入口。conv_id 标识对话（前端生成），用于澄清槽位的挂起与恢复。

    澄清是逐槽位多轮的：每轮只问一个缺失槽位，直到物料+现象都清楚
    （或用户点"不用问了，直接回答"）。规则见 docs/agent-workflow.md。
    on_status 为可选的流式状态回调（str → None），每个真实执行动作前调用
    （/api/agent/chat/stream 用它推过程状态，非流式调用传 None 即可）。
    file_context 为可选的多模态文件上下文：{"type": "text"|"image", "text": str, "base64": str, "mime": str, "filename": str}。
    """
    if conv_id not in _CONV and len(_CONV) >= _MAX_CONV_STATES:
        # 内存演示规模：只保留最近活跃的会话状态，防止长期运行越积越多
        oldest = min(_CONV.items(), key=lambda kv: kv[1].get("last_ts", 0) or 0)[0]
        _CONV.pop(oldest, None)
    state = _CONV.setdefault(conv_id, {})
    state["last_ts"] = time.time()

    # 多模态文件上下文：有文件时先记录状态，并把文件内容注入消息
    raw_message = message  # 注入前的原始消息（投稿意图判定只认用户原话，防注入文本里的"上传/笔记"误判）
    if file_context:
        filename = file_context.get("filename", "未命名文件")
        ftype = file_context.get("type")
        if ftype == "image":
            state["last_file"] = {"type": "image", "filename": filename,
                                  "base64": file_context.get("base64"), "mime": file_context.get("mime", "image/jpeg")}
            message = f"{message}\n[用户上传了图片：{filename}]"
        elif ftype == "text":
            text = file_context.get("text", "")[:2000]  # 文本太长截断，防 token 爆炸
            state["last_file"] = {"type": "text", "filename": filename, "text": text}
            message = f"{message}\n[用户上传了文件：{filename}]\n文件内容：\n{text}"
        on_status = on_status or _noop_status
        on_status(f"已接收并解析上传文件：{filename}")

    # 带附件的新提问（非澄清补充）：文件本身就是问题主体，
    # 跳过意图识别与槽位澄清，直接按文件内容回答（"这是什么"不该被反问"哪个物料"）
    if file_context and not state.get("pending"):
        # 投稿意图（"上传 RV1126B 的参考文档"）→ 提炼后转入资料审核队列
        if _is_contribute(raw_message):
            return _contribute(db, user_id, raw_message, [], on_status, file_context)
        return _file_answer(db, message, [], on_status, file_context)

    # 投稿意图但本轮没带附件：沿用对话里最近上传的附件（"那上传到你的数据库里吧"）
    if not file_context and not state.get("pending") and _is_contribute(message):
        last_file = state.get("last_file")
        if last_file:
            steps = [{"step": "上下文接续",
                      "detail": f"沿用上一轮附件「{last_file.get('filename', '未命名')}」执行投稿"}]
            return _contribute(db, user_id, message, steps, on_status or _noop_status, last_file)
        # 对话里也没有附件：引导用输入栏左侧回形针选择文件
        return _resp(0, "ok", {
            "intent": "contribute",
            "steps": [{"step": "意图识别", "detail": "识别为「投稿资料」，但未检测到附件"}],
            "answer": "好的，欢迎分享！请点输入栏左侧的回形针按钮选择要上传的资料文件"
                      "（支持图片/PDF/Word/TXT），再发送一次这句话，我会提炼要点后提交管理员审核。",
            "references": [], "provenance": None, "clarify": None,
        })

    pending = state.pop("pending", None)
    if pending:
        slots = pending.get("slots") or {}
        original = pending["message"]
        awaiting = pending.get("awaiting")

        # 逃生项：用户选择跳过澄清，按已有信息直接回答
        if message == _ESCAPE_OPTION:
            steps = [{"step": "用户选择直接回答", "detail": "按当前已知信息处理"}]
            return _dispatch(db, user_id, original, steps, state,
                             allow_clarify=False, forced_intent=pending["intent"], slots=slots,
                             on_status=on_status, file_context=file_context)

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
            if message == _OTHER_PHENOMENON_OPTION:
                # "其他"只是排除了候选项，必须再追问自由描述，拿到描述才算槽位齐备
                return _clarify(state, pending["intent"], original, slots, "phenomenon_free",
                                steps, [_ESCAPE_OPTION],
                                "好的，那具体是什么现象？用一句话描述（如：上电完全没反应、转两下就停、读数一直是 0）")
            slots["phenomenon"] = message
        elif awaiting == "phenomenon_free":
            slots["phenomenon"] = message
        # 槽位推进后重入流程：还有缺失槽位会继续问，齐了自然回答
        return _dispatch(db, user_id, original, steps, state,
                         allow_clarify=True, forced_intent=pending["intent"], slots=slots,
                         on_status=on_status, file_context=file_context)
    # 跨轮次上下文：短指代消息（"那怎么接线""它还能干嘛"）沿用上一轮定位到的物料
    followup = _followup_slots(state, message)
    if followup and state.get("last", {}).get("intent") in ("troubleshoot", "explore"):
        last = state["last"]
        steps = [{"step": "上下文接续", "detail": f"沿用上一轮物料「{last['material_name']}」"}]
        return _dispatch(db, user_id, message, steps, state,
                         allow_clarify=True, forced_intent=last["intent"], slots=followup,
                         on_status=on_status, file_context=file_context)

    return _dispatch(db, user_id, message, [], state, allow_clarify=True, forced_intent=None,
                     on_status=on_status, file_context=file_context)
