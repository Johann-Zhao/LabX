"""LLM 调用统一封装（DeepSeek，OpenAI 兼容接口）。

配置读 backend/.env（格式见 .env.example）：
- LABX_API_KEY / LABX_API_BASE / LABX_MODEL
- LABX_LLM_MOCK=true 时所有调用返回预置兜底答案（演示断网也能跑，见 NFR2）

注意：deepseek-v4-flash 带推理链，max_tokens 要给足，别卡太小。
"""
import os

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


def chat(system: str, user: str, max_tokens: int = 1024) -> str:
    """单轮问答，返回文本。任何异常都降级为兜底答案，绝不向上抛。"""
    if MOCK or not API_KEY:
        return MOCK_ANSWER
    try:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=30)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip() or MOCK_ANSWER
    except Exception as e:  # 网络不通、key 失效、超时等一律兜底
        return f"{MOCK_ANSWER}\n（LLM 调用失败已降级：{type(e).__name__}）"
