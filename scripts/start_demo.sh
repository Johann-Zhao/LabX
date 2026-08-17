#!/usr/bin/env bash
# LabX 最终演示一键启动（Git Bash）：
#   bash scripts/start_demo.sh
# 后端 http://127.0.0.1:8000/docs，前端 http://localhost:5173
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "[LabX] 启动后端 uvicorn ..."
(cd "$ROOT/backend" && ./venv/Scripts/python -m uvicorn main:app --host 0.0.0.0 --port 8000) &
BACK_PID=$!

echo "[LabX] 启动前端 vite ..."
(cd "$ROOT/frontend" && npm run dev) &
FRONT_PID=$!

cleanup() {
  echo "[LabX] 停止服务..."
  kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true
}
trap cleanup INT TERM

echo "[LabX] 就绪：前端 http://localhost:5173 ｜ 后端 http://127.0.0.1:8000/docs"
echo "[LabX] 按 Ctrl+C 同时停止前后端"
wait
