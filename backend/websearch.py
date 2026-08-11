"""极简联网检索：DuckDuckGo HTML 版，无需 API key。

用途：本地知识库未命中时的兜底检索（见 docs/agent-workflow.md）。
任何失败都返回空列表，由调用方降级到"通用经验"回答，绝不向上抛异常。
"""
import re
from urllib.parse import unquote

import httpx

_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LabX/1.0"}

# 官方/权威资料域名（联网检索结果优先采用，见 docs/agent-workflow.md）
_OFFICIAL_DOMAINS = (
    "arduino.cc", "espressif.com", "st.com", "raspberrypi.com", "adafruit.com",
    "dfrobot.com", "vishay.com", "sparkfun.com", "micropython.org", "stcmicro.com",
    "hakko.com", "ti.com", "microchip.com", "docs.rs", "wikipedia.org",
)


def _is_official(url: str) -> bool:
    return any(d in url for d in _OFFICIAL_DOMAINS)


def _clean(html_fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html_fragment)).strip()


def _decode_ddg_link(url: str) -> str:
    """DuckDuckGo 结果链接是 //duckduckgo.com/l/?uddg=<真实URL> 的跳转，解出真实地址。"""
    m = re.search(r"uddg=([^&]+)", url)
    return unquote(m.group(1)) if m else url


def web_search(query: str, max_results: int = 3) -> list[dict]:
    """返回 [{title, snippet, url}]，官方资料域名排前面。无结果或失败返回 []。"""
    try:
        resp = httpx.get(_DDG_URL, params={"q": query}, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        html = resp.text
        # 结果块：标题链接 class="result__a"，摘要 class="result__snippet"
        items = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
        results = []
        for (url, title), snippet in zip(items[: max_results * 2], snippets[: max_results * 2]):
            results.append({
                "title": _clean(title),
                "snippet": _clean(snippet),
                "url": _decode_ddg_link(url),
            })
        # 官方域名优先（稳定排序，保持同类内部原有顺序）
        results.sort(key=lambda r: not _is_official(r["url"]))
        return results[:max_results]
    except Exception:
        return []
