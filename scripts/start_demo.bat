@echo off
REM LabX 最终演示一键启动（Windows 双击）
cd /d "%~dp0.."
start "LabX 后端 :8000" cmd /k "cd backend && venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000"
start "LabX 前端 :5173" cmd /k "cd frontend && npm run dev"
echo LabX 已启动：前端 http://localhost:5173 ｜ 后端 http://127.0.0.1:8000/docs
pause
