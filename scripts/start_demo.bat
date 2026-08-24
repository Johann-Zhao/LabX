@echo off
chcp 65001 >nul
setlocal
REM LabX 演示一键启动（Windows 双击）——带启动前检查与就绪等待
cd /d "%~dp0.."
title LabX 启动器

echo ============================================
echo  LabX 启动前检查
echo ============================================

REM ---- 1. Python 虚拟环境 ----
if not exist "backend\venv\Scripts\python.exe" (
    echo.
    echo [失败] 未找到 Python 虚拟环境：backend\venv
    echo        请先执行：
    echo          cd backend
    echo          python -m venv venv
    echo          venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
echo [通过] Python 虚拟环境

REM ---- 2. 前端依赖 ----
if not exist "frontend\node_modules" (
    echo.
    echo [失败] 未安装前端依赖：frontend\node_modules 不存在
    echo        请先执行：
    echo          cd frontend
    echo          npm install
    pause
    exit /b 1
)
echo [通过] 前端依赖

REM ---- 3. 端口占用 ----
netstat -ano | findstr "LISTENING" | findstr /C:":8000 " >nul
if %errorlevel%==0 (
    echo.
    echo [失败] 端口 8000 已被占用（后端需要使用）
    echo        请执行 netstat -ano ^| findstr :8000 找到 PID 后关闭该进程
    pause
    exit /b 1
)
echo [通过] 端口 8000 空闲

netstat -ano | findstr "LISTENING" | findstr /C:":5173 " >nul
if %errorlevel%==0 (
    echo.
    echo [失败] 端口 5173 已被占用（前端需要使用）
    echo        请执行 netstat -ano ^| findstr :5173 找到 PID 后关闭该进程
    pause
    exit /b 1
)
echo [通过] 端口 5173 空闲

REM ---- 4. 后端配置 ----
if not exist "backend\.env" (
    echo.
    echo [失败] 未找到后端配置文件：backend\.env
    echo        请复制 backend\.env.example 为 .env 并填写 LABX_API_KEY
    echo        （断网演示可只写一行 LABX_LLM_MOCK=true）
    pause
    exit /b 1
)
echo [通过] 后端配置 .env

echo ============================================
echo  检查通过，正在启动服务
echo ============================================

REM ---- 5. 先启动后端并等待就绪 ----
echo 正在启动后端（LabX 后端 :8000）...
start "LabX 后端 :8000" cmd /k "cd backend && venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000"

set /a tries=0
:wait_backend
curl -s -o nul http://127.0.0.1:8000/api/ping
if %errorlevel%==0 goto backend_ready
set /a tries+=1
if %tries% geq 30 (
    echo.
    echo [失败] 后端 30 秒内未就绪
    echo        请查看“LabX 后端 :8000”窗口中的报错信息
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_backend
:backend_ready
echo [通过] 后端已就绪

REM ---- 6. 后端就绪后再启动前端并等待 ----
echo 正在启动前端（LabX 前端 :5173）...
start "LabX 前端 :5173" cmd /k "cd frontend && npm run dev"

set /a tries=0
:wait_frontend
curl -s -o nul http://127.0.0.1:5173
if %errorlevel%==0 goto frontend_ready
set /a tries+=1
if %tries% geq 30 (
    echo.
    echo [失败] 前端 30 秒内未就绪
    echo        请查看“LabX 前端 :5173”窗口中的报错信息
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_frontend
:frontend_ready
echo [通过] 前端已就绪

REM ---- 7. 自动打开浏览器 ----
echo.
echo LabX 已启动：前端 http://localhost:5173 ｜ 后端 http://127.0.0.1:8000/docs
echo 正在打开浏览器...
start http://localhost:5173
pause
