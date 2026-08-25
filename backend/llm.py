"""LLM 调用统一封装（DeepSeek，OpenAI 兼容接口）。

配置读 backend/.env（格式见 .env.example）：
- LABX_API_KEY / LABX_API_BASE / LABX_MODEL
- LABX_LLM_MOCK=true 时所有调用返回预置兜底答案（演示断网也能跑，见 NFR2）

注意：deepseek-v4-flash-vision-exp 带推理链且支持图片输入，max_tokens 要给足，别卡太小。
"""
import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

API_KEY = os.getenv("LABX_API_KEY", "")
BASE_URL = os.getenv("LABX_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("LABX_MODEL", "deepseek-v4-flash-vision-exp")
MOCK = os.getenv("LABX_LLM_MOCK", "false").strip().lower() == "true"

# 断网/无 key 时的兜底回答（通用排查建议，不绑定具体物料）
MOCK_ANSWER = (
    "（离线兜底回答）AI 服务暂时不可用。通用建议："
    "1) 先断电重启，排除偶发死机；2) 检查供电与接线（八成的问题出在这）；"
    "3) 打开对应物料的详情页，按「三分钟上手」和「常见错误」卡片逐项核对。"
)


def chat(system: str, user: str, max_tokens: int = 1024, fallback: str | None = MOCK_ANSWER,
         timeout: int = 30) -> str | None:
    """单轮问答，返回文本。任何异常都降级为 fallback，绝不向上抛。

    fallback 默认为通用兜底答案（问答场景直接用）；
    传 None 表示调用方要自己区分"LLM 不可用"（如 BOM 生成会退回关键词匹配）。
    timeout：长输出场景（如 BOM 全量 JSON）要放宽，v4-flash 推理链耗时大。
    """
    if MOCK or not API_KEY:
        return fallback
    for _attempt in range(2):  # 校园网偶发连接重置（WinError 10054），白嫖一次重试（重置 fail-fast 不耗时）
        try:
            client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=timeout)
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip() or fallback
        except Exception:  # 网络不通、key 失效、超时等一律兜底
            continue
    return fallback

def chat_with_image(system: str, user_text: str, image_base64: str,
                    image_mime: str = "image/jpeg", max_tokens: int = 1024,
                    fallback: str | None = MOCK_ANSWER, timeout: int = 45) -> str | None:
    """多模态问答：文本 + 图片（base64），返回文本。任何异常都降级为 fallback，绝不向上抛。

    image_base64：图片的 base64 编码字符串（不含 data: 前缀）。
    image_mime：图片 MIME 类型，如 image/jpeg / image/png / image/webp。
    """
    if MOCK or not API_KEY:
        return fallback
    data_url = f"data:{image_mime};base64,{image_base64}"
    for _attempt in range(2):
        try:
            client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=timeout)
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ]},
                ],
                max_tokens=max_tokens,
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                return content
            # vision-exp 推理链偶尔把 max_tokens 预算烧完导致正文为空（finish_reason=length），重试一次
            continue
        except Exception:
            continue
    return fallback


def chat_with_search(system: str, user: str, max_tokens: int = 1024) -> str | None:
    """DeepSeek Responses API 原生联网搜索（tools=web_search，无需第三方搜索 key）。

    成功返回回答文本；任何失败返回 None，由调用方降级（DuckDuckGo/通用经验）。
    v4-flash 偶发把输出预算全烧在"搜索→无结果→再搜索"循环上（status=incomplete、没有 message 项），
    这种"无正文"结果重试一次，其余失败直接放弃。
    """
    if MOCK or not API_KEY:
        return None
    base = BASE_URL.removesuffix("/v1")  # https://api.deepseek.com
    # 重试 3 次：①200 但无正文（预算烧在搜索循环上）②校园网偶发连接重置（WinError 10054，fail-fast 不耗时）
    for _attempt in range(3):
        try:
            resp = httpx.post(
                f"{base}/responses",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": MODEL,
                    "instructions": system,
                    "input": user,
                    "tools": [{"type": "web_search"}],
                    "max_output_tokens": max_tokens,
                },
                timeout=45,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            for item in reversed(data.get("output", [])):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text" and c.get("text"):
                            return c["text"].strip()
            # 200 但没产出正文（预算烧在搜索循环上）→ 重试一次
        except Exception:
            continue
    return None
