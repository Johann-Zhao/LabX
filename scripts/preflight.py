# -*- coding: utf-8 -*-
"""LabX 最终展示前自检脚本。

用法：backend/venv/Scripts/python scripts/preflight.py
检查后端与前端是否就绪、数据库是否已灌入演示数据、账号能否登录、
智能助手最小调用是否可通。任何一项失败都会在末尾给出 FAIL 提示。
"""
import json
import os
import sys
import time

import httpx

BACKEND = "http://127.0.0.1:8000"
FRONTEND = "http://127.0.0.1:5173"


def post(path, payload, timeout=60):
    return httpx.post(BACKEND + path, content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=timeout, trust_env=False)


def get(path, timeout=15):
    return httpx.get(BACKEND + path, timeout=timeout, trust_env=False)


def main() -> int:
    failures: list[str] = []

    def check(name, ok, extra=""):
        print(("PASS  " if ok else "FAIL  ") + name + (f"  {extra}" if extra else ""))
        if not ok:
            failures.append(name)

    # 1. 后端存活
    try:
        r = get("/api/ping", timeout=5)
        check("后端 /api/ping", r.status_code == 200 and r.json().get("msg") == "pong")
    except Exception as e:
        check("后端 /api/ping", False, repr(e))

    # 2. 演示数据
    try:
        mats = get("/api/materials").json().get("data", [])
        check("物料数据", len(mats) >= 15, f"{len(mats)} 件")
        low = [m["material_id"] for m in mats if m["available_quantity"] <= 2]
        check("低库存预警素材", bool(low), "、".join(low) if low else "无低库存物料")
    except Exception as e:
        check("物料数据", False, repr(e))

    try:
        users = get("/api/users").json().get("data", [])
        check("用户数据", len(users) >= 3, f"{len(users)} 个")
    except Exception as e:
        check("用户数据", False, repr(e))

    # 3. 登录
    try:
        r = post("/api/auth/login", {"user_id": "2024001", "password": "123456"})
        d = r.json()
        check("学生登录", r.status_code == 200 and d.get("code") == 0 and d["data"]["role"] == "student")
    except Exception as e:
        check("学生登录", False, repr(e))
    try:
        r = post("/api/auth/login", {"user_id": "admin", "password": "admin888"})
        d = r.json()
        check("管理员登录", r.status_code == 200 and d.get("code") == 0 and d["data"]["role"] == "admin")
    except Exception as e:
        check("管理员登录", False, repr(e))

    # 4. 智能助手最小调用（纯打招呼，不烧 LLM 网络检索）
    try:
        t = time.time()
        r = post("/api/agent/chat", {"user_id": "2024001", "message": "你好", "conv_id": "preflight"})
        d = r.json()
        ok = r.status_code == 200 and d.get("code") == 0 and bool(d.get("data", {}).get("answer"))
        check("智能助手最小调用", ok, f"{time.time() - t:.1f}s")
    except Exception as e:
        check("智能助手最小调用", False, repr(e))

    # 5. 前端静态服务（vite 已启动时）
    try:
        r = httpx.get(FRONTEND + "/", timeout=5, trust_env=False)
        check("前端 http://localhost:5173", r.status_code == 200)
    except Exception as e:
        check("前端 http://localhost:5173", False, "未启动则先用 scripts/start_demo 启动")

    print("\n" + ("全部通过，可以开始演示。" if not failures else f"有 {len(failures)} 项未通过：{failures}"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
