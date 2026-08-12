# -*- coding: utf-8 -*-
"""Seedream 5.0 Pro 单张图片生成脚本（演示素材用，不改业务代码）。

用法（工作目录 backend/）：
    ./venv/Scripts/python scripts/seedream_gen.py \
        --prompt "..." --out ../deta/images/intro/hero.png \
        --size 2048x1152,1152x864,1024x1024

- 手动解析 backend/.env 里的 SEEDREAM_API_KEY / SEEDREAM_API_BASE / SEEDREAM_MODEL
- --size 支持逗号分隔多个候选，接口报尺寸不支持时依次尝试
- 校验 PNG magic bytes 且文件 > 30KB，失败重试 3 次，每次自动简化 prompt
- 网络走 httpx.Client(trust_env=False)，直连失败自动回退 trust_env=True
"""
import argparse
import base64
import os
import sys
import time

import httpx

# backend/ 目录（本脚本在 backend/scripts/ 下）
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BACKEND_DIR, ".env")

MIN_BYTES = 30 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
NO_TEXT_SUFFIX = "无文字，无水印，无logo"


def load_env():
    """手动解析 .env（python-dotenv 不一定装，且只要三个变量）。"""
    cfg = {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("SEEDREAM_API_KEY", "SEEDREAM_API_BASE", "SEEDREAM_MODEL"):
        if not cfg.get(key):
            raise RuntimeError(f".env 缺少 {key}")
    return cfg


def simplify_prompt(prompt, attempt):
    """第 attempt 次重试时按逗号分句裁掉尾部细节，保留无文字后缀。"""
    if attempt <= 0:
        return prompt
    clauses = [c for c in prompt.split("，") if c.strip()]
    keep = max(3, len(clauses) - attempt * 2)
    kept = clauses[:keep]
    if not any(NO_TEXT_SUFFIX.split("，")[0] in c for c in kept):
        kept.append(NO_TEXT_SUFFIX)
    return "，".join(kept)


def _post(client, url, headers, body):
    return client.post(url, headers=headers, json=body)


def request_image(cfg, prompt, size):
    """调 Seedream 接口，返回 PNG 字节；尺寸不支持抛 SizeError 供上层换尺寸。"""
    url = cfg["SEEDREAM_API_BASE"].rstrip("/") + "/images/generations"
    headers = {
        "Authorization": f"Bearer {cfg['SEEDREAM_API_KEY']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": cfg["SEEDREAM_MODEL"],
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
        "watermark": False,
        # seedream 默认返回 JPEG，必须显式要 PNG（实测验证）
        "output_format": "png",
    }
    last_exc = None
    for trust_env in (False, True):
        try:
            with httpx.Client(trust_env=trust_env, timeout=120) as client:
                resp = _post(client, url, headers, body)
                if resp.status_code != 200:
                    text = resp.text[:500]
                    if "size" in text.lower() or "param" in text.lower():
                        raise SizeError(f"尺寸 {size} 不被接受: {text}")
                    raise RuntimeError(f"HTTP {resp.status_code}: {text}")
                payload = resp.json()
                if "error" in payload and payload["error"]:
                    raise RuntimeError(f"接口报错: {str(payload['error'])[:500]}")
                item = (payload.get("data") or [{}])[0]
                if item.get("b64_json"):
                    return base64.b64decode(item["b64_json"])
                if item.get("url"):
                    # url 有时效，立刻用同一 client 下载
                    r2 = client.get(item["url"])
                    r2.raise_for_status()
                    return r2.content
                raise RuntimeError(f"返回里既没有 b64_json 也没有 url: {str(payload)[:500]}")
        except SizeError:
            raise
        except (httpx.ProxyError, httpx.ConnectError, httpx.ConnectTimeout) as e:
            last_exc = e
            print(f"  [net] trust_env={trust_env} 连接失败({type(e).__name__})，换通道重试")
            continue
    raise RuntimeError(f"网络连接失败: {last_exc}")


class SizeError(Exception):
    pass


def generate(prompt, out_path, sizes, max_retry=3, verbose=True):
    """生成一张图并落盘。返回 (ok, out_path, bytes_written, used_size, note)。"""
    cfg = load_env()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    if isinstance(sizes, str):
        sizes = [s.strip() for s in sizes.split(",") if s.strip()]

    note = ""
    for attempt in range(max_retry):
        p = simplify_prompt(prompt, attempt)
        if attempt > 0 and verbose:
            print(f"  [retry {attempt}] 简化 prompt: {p[:60]}...")
        for size in sizes:
            try:
                data = request_image(cfg, p, size)
            except SizeError as e:
                note = str(e)
                if verbose:
                    print(f"  [size] {note[:120]}，换下一尺寸")
                continue
            except Exception as e:
                note = f"attempt{attempt} size={size}: {e}"
                if verbose:
                    print(f"  [fail] {note[:200]}")
                time.sleep(2)
                break  # 网络/服务错误直接进下一次重试（简化 prompt）
            # 校验
            if not data.startswith(PNG_MAGIC):
                note = f"返回不是 PNG（前8字节={data[:8]!r}）"
                if verbose:
                    print(f"  [bad] {note}")
                continue
            if len(data) < MIN_BYTES:
                note = f"PNG 过小（{len(data)}B < {MIN_BYTES}B），疑似空白图"
                if verbose:
                    print(f"  [bad] {note}")
                continue
            with open(out_path, "wb") as f:
                f.write(data)
            return True, out_path, len(data), size, note
        time.sleep(1)
    return False, out_path, 0, "", note


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1024x1024",
                    help="逗号分隔多个候选尺寸，依次尝试")
    args = ap.parse_args()
    ok, out, nbytes, size, note = generate(args.prompt, args.out, args.size)
    if ok:
        print(f"OK {out} {nbytes // 1024}KB size={size}")
        sys.exit(0)
    print(f"FAIL {out}: {note}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
