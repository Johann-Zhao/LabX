# LabX

面向学生创新实践的体验型智能体 —— 物料借还 + 借用即学习 + 知识随物 + 社区经验闭环。

## 仓库结构

| 目录 | 内容 | 负责人 |
|---|---|---|
| `frontend/` | Vue 3 + Vite 前端 | 成员 A |
| `backend/` | FastAPI 后端 + MCP Server + RAG | 成员 B |
| `deta/` | 演示数据、知识卡片、文档（目录名沿用仓库现状） | 成员 C |
| `API.md` | 前后端接口契约（B 维护，变更先在群里同步） | 全员遵守 |

## 快速启动

```bash
# 后端（第一次先建环境）
cd backend
python -m venv venv
source venv/Scripts/activate        # Git Bash；CMD 用 venv\Scripts\activate
pip install -r requirements.txt
python init_db.py                   # 建表 + 灌入样例物料/用户（C 给了 deta/materials.csv 后重新跑即导入）
uvicorn main:app --reload           # http://127.0.0.1:8000/docs 可在线看接口文档

# 前端（另开一个终端）
cd frontend
npm install
npm run dev                         # 浏览器打开 http://localhost:5173
```

浏览器打开即是物料列表页：点进物料 → 确认借用 → 库存减 1 → "我的借用"里归还 → 库存加 1（v0.1 验收链路）。

手机调试：手机与电脑连同一 WiFi，访问 `http://<电脑局域网IP>:5173`。前端统一走相对路径 `/api` + vite proxy 转发，**不要**把 axios 的 baseURL 写死成 localhost。

## 协作约定（摘自团队指南）

- 开工先拉、能跑才推、收工必推；按目录分地盘，动别人地盘或共用文件（README、API.md）先在群里说一声
- LLM API key 只写在 `backend/.env`（参照 `backend/.env.example`），`.env` 已被 `.gitignore` 排除，绝不提交
- 假接口先行：后端接口先按 `API.md` 返回假数据，前端不等后端真实现
