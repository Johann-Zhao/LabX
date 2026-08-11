"""LLM 调用统一封装（DeepSeek，OpenAI 兼容接口）。

配置读 backend/.env（格式见 .env.example）：
- LABX_API_KEY / LABX_API_BASE / LABX_MODEL
- LABX_LLM_MOCK=true 时所有调用返回预置兜底答案（演示断网也能跑，见 NFR2）

注意：deepseek-v4-flash 带推理链，max_tokens 要给足，别卡太小。
"""
import os

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

API_KEY = os.getenv("LABX_API_KEY", "")
BASE_URL = os.getenv("LABX_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.getenv("LABX_MODEL", "deepseek-v4-flash")
MOCK = os.getenv("LABX_LLM_MOCK", "false").strip().lower() == "true"

# 断网/无 key 时的兜底回答（对应最高频演示问题：DHT22 读数为 0）
MOCK_ANSWER = (
    "（离线兜底回答）最常见的原因是数据脚没接上拉电阻。请检查："
    "1) DATA 脚接 4.7kΩ 上拉电阻到 VCC；2) 用示例代码自检；"
    "3) 确认供电 3.3-5V、两次读取间隔大于 2 秒。"
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
        return fallback


def chat_with_search(system: str, user: str, max_tokens: int = 1024) -> str | None:
    """DeepSeek Responses API 原生联网搜索（tools=web_search，无需第三方搜索 key）。

    成功返回回答文本；任何失败返回 None，由调用方降级（DuckDuckGo/通用经验）。
    """
    if MOCK or not API_KEY:
        return None
    base = BASE_URL.removesuffix("/v1")  # https://api.deepseek.com
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
            return None
        data = resp.json()
        for item in reversed(data.get("output", [])):
            if item.get("type") == "message":
                for c in item.get("content", []):
                    if c.get("type") == "output_text" and c.get("text"):
                        return c["text"].strip()
        return None
    except Exception:
        return None
