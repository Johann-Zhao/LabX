# AGENTS.md —— LabX 开发约束（AI 与人共同遵守）

> 本文件是仓库级开发规范。AI 每次开工前先读本文件，再读 `API.md`。
> 源头文档（在本机，不进仓库）：《LabX方案（可编辑版）.md》（设计spec，含附录A数据模型）、《LabX实现技术方案与团队指南.md》（实施spec，阶段0-4任务拆解）。本文件与它们冲突时，以两份spec为准并更新本文件。

## 1. 项目一句话

LabX：面向高校创新空间的体验型智能体——物料借还 + 借用触发知识推送 + RAG问答 + 社区经验闭环。8月22日交付 P0+P1 可演示闭环。

## 2. 目录分工（按地盘改代码，动别人地盘先打招呼）

| 目录 | 内容 | 负责人 |
|---|---|---|
| `frontend/` | Vue 3 + Vite + Element Plus 前端 | 队长（成员A职责） |
| `backend/` | FastAPI + SQLite + Chroma + MCP | 队长（成员B职责） |
| `deta/` | 演示数据、知识卡片、测试checklist | 成员 C，队长不动 |
| `API.md` | 前后端唯一接口契约 | 后端改，变更先同步 |

## 3. 技术栈与关键决策（不许跑偏）

- 前端：Vue 3（`<script setup>`）+ Vite + Element Plus（全量引入）+ axios + Vue Router。**一套响应式页面**，不做小程序、不做双UI库。
- 后端：Python 3.13 + FastAPI + SQLAlchemy + SQLite（单文件 `backend/labx.db`，不上 PostgreSQL）。
- 向量库：Chroma（本地持久化 `backend/.chroma/`，阶段 2 接入）。
- LLM：DeepSeek（OpenAI 兼容接口），配置只读 `backend/.env`：`LABX_API_KEY / LABX_API_BASE / LABX_MODEL=deepseek-v4-flash / LABX_LLM_MOCK`。
  - 注意：v4-flash 带推理链（reasoning_content），JSON 输出类 prompt 的 max_tokens 要给足。
  - 所有 LLM 调用必须走统一封装（阶段 2 的 `llm.py`），尊重 `LABX_LLM_MOCK` 断网兜底开关。
- 物料**不贴任何实体标签**（无 RFID/二维码），去向以借用记录为准。
- MCP：阶段 2 用 FastMCP 把 material/knowledge 接口薄封装成 MCP Server；编排引擎就是 FastAPI 里的一个 Python 模块，不搞分布式。
- 离线模式、本地 LLM、智能柜硬件：P3 展望，**只写文档不写代码**。

## 4. 开发命令

```bash
# 后端（Git Bash）
cd backend && source venv/Scripts/activate
python init_db.py                 # 建表 + 灌入样例/CSV 数据（可重复跑，会先清库）
uvicorn main:app --reload         # http://127.0.0.1:8000/docs 可看接口文档

# 前端
cd frontend && npm run dev        # http://localhost:5173，/api 由 vite proxy 转发到 8000
```

## 5. 接口契约纪律

- `API.md` 是唯一契约：前端只信 API.md，后端实现对齐 API.md。**改契约 = 先改 API.md 再改代码。**
- 统一返回 `{ "code": 0, "msg": "...", "data": ... }`；业务错误码表在 API.md 文末，新增错误码要登记。
- 前端 axios 一律用相对路径 `/api`（vite proxy 转发），**禁止写死 localhost/IP**（手机调试会断）。

## 6. 代码风格

- 注释、commit message 用中文，说清"做了什么"；标识符用英文。
- 后端：一个文件一个职责（`main.py` 接口层 / `db.py` 模型 / `init_db.py` 数据初始化 / 后续 `llm.py`、`rag.py`、`mcp_servers/`）。接口函数要短，状态机逻辑集中写，不散落各处。
- 前端：页面放 `src/views/`，可复用组件放 `src/components/`，axios 实例统一在 `src/api.js`。
- 新手团队可读性优先：不过度抽象、不提前优化、不加 spec 没要求的功能（YAGNI）。

## 7. Git 纪律

- **每个环节一 commit**（队长明确要求，授权 AI 执行）：完成一个可验证的小步就提交，message 格式 `阶段X：做了什么`。
- 绝不提交 `.env`（API key）；绝不 force push；绝不删 `.git`。
- push 到 origin 需队长明确发话（本地 commit 不需要）。
- 提交前必须验证该环节能跑通（见第 8 节）， Reds 不进库。

## 8. 验证要求（每个环节提交前）

- 后端改动：重启 uvicorn，用 curl 把改动涉及的接口实际调一遍（含错误分支），预期结果对齐 API.md。
- 前端改动：`npm run dev` 起服务，真实浏览器走一遍涉及页面（可用 Playwright 自动化点击验证）。
- 中文测试数据用 UTF-8 文件 POST（Git Bash 的 curl 内联中文会变 GBK 导致 400，是终端问题不是 bug）。
- 阶段验收标准以《团队指南》为准（v0.1 / v0.2 / v1.0）。

## 9. 当前进度（每完成一个环节就更新这里）

- [x] 阶段 0：骨架 + API 契约 + 假接口（commit `5f39399`）
- [x] 阶段 1：借还 MVP —— 三表 + 真实借还接口 + 前端四页面，v0.1 浏览器走查通过（commits `d04427b`/`4e8b18d`/`2dbb569`）
- [x] 阶段 2：知识服务 —— 33 卡片入库、借用返回真卡片、RAG 问答（本地 n-gram 向量 + DeepSeek）、FastMCP 双 Server、前端问答页，v0.2 浏览器走查通过（commits `2a68970`/`a0af620`/`b5f76f9` 起）
- [x] 阶段 3：智能体编排 —— 编排引擎（意图分类+排障五步调用链）、分级权限（1002/1003 已生效）、BOM 接真实 LLM、归还心得草稿+经验入库（社区闭环打通）、user-mcp、前端 BOM 页/智能体对话/心得弹窗/安全确认/用户切换，v1.0 四幕剧本浏览器走查通过（commits `c19600f`/`a7f4522`）
- [ ] 阶段 4：演示数据灌满 + 全流程测试 + 部署固化 + 录视频 ← **当前在这里**

**阶段 4 待办细节**（做完划掉）：
1. 物料照片：用 Seedream 批量生成 11 张物料图（prompt 教训：不写"45度俯拍"等数字角度、加"无文字无水印"），存 `deta/images/`，物料表/前端挂图
2. 3 个往期项目（含 BOM、心得、照片）+ 5 条预置社区经验（写进 deta/，init_db 灌入）
3. 故障博物馆：烧坏的 Arduino 实物 + 手写"死因卡"（线下道具，队长/队员准备）
4. 全流程测试 checklist（存 `deta/checklist.md`）真机走三遍：借还、问答、BOM、排障、归还、换账号
5. 部署固化：一台笔记本跑全部服务 + 启动脚本；断网演示预案（`LABX_LLM_MOCK=true`）
6. 录制完整演示视频（防现场翻车）+ 5 分钟剧本排练
7. 前端美化（队长指示：先不急，功能稳定后再做）：大屏适配、动效
