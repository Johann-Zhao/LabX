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
- 智能体对话的交互规则（澄清优先、本地→联网→通用阶梯、provenance 标注）见 `docs/agent-workflow.md`，改对话行为先改它再改 `orchestrator.py`。

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
- [x] 交互升级：对话工作流规范（`docs/agent-workflow.md`）落地——澄清优先（槽位不足先反问给候选）、本地→联网→通用→离线回答阶梯（IDF 重排阈值判定本地命中）、provenance 徽标、问答与愿望到方案融合为智能助手页（commits `8cea306`/`2b1f841`/`d212341`）
- [x] 愿望到方案 v2 + 借期分级审核：BOM 全链路重构（LLM 自由列完整清单 8-15 件并自行标 catalog_id，后端校验防幻觉；plan 4-6 步放气泡正文；卡片分"实验室可借/需自行购买"两组；接不住的愿望如造火箭→幽默回应+替代建议）；借用加 days/reason/quantity——≤30 天直接借出，>30 天必填理由（1006）转人工审核（pending 不扣库存，`/api/borrow/review` 通过才扣库存起算借期）；一条记录记 quantity 件；前端 BorrowDialog 借期弹窗接入一键预约与详情页单借（commits `c67c65e` 起）
- [x] 管理员页面 `/admin`：待审核（角标计数，通过/驳回超期申请，驳回二次确认）、借用中（物料当前持有人一览表）、全部流水（五态卡片：借用人/借出/应还/实还）；流水接口记录加 `user_name` 字段（commits `c67c65e`/`bb0752c` 起）
- [x] explore 意图 + 过程显化：新增"物料求用法"意图（有物料不知怎么用→只问物料不问现象，①它是什么②能做什么③上手第一步④深入学习入口，自带物料联网检索+配套建议优先提实验室目录件）；`/api/agent/chat/stream` 流式推送真实执行状态，前端待定气泡逐行显化+跳动圆点动画（commits `9deb1d6` 起）
- [x] 管理端独立管理台 `/admin`：与学生端分离的左右布局（左侧功能栏：审核申请/当前在借/全部流水/批量借出/录入物料，右侧内容区）；批量借出（选学生+勾选多件+数量，一次借出，逐件结果）；录入物料（分类前缀自动编号，名称去重）；新增 `/api/borrow/batch`、`/api/materials` 接口（commits `994dc49` 起）
- [x] UI/UX 重构（学生端）：设计规范 `docs/design/labx-ui.md` + 令牌 `tokens.css` + Element 主题覆盖（蒸馏自 GitHub 高星 skill：Leonxlnx/taste-skill 75.6k★、pbakaus/impeccable 58.4k★）；开屏深色介绍动画（`IntroOverlay.vue`，canvas 粒子星座 + Seedream 四幕视觉，仅首次播放可跳过 localStorage 标记，图片缺失优雅降级，prefers-reduced-motion 降级）；智能助手升为首页 `/`（物料移到 `/materials`，`/ask` 重定向，空状态常用提问 chips，宽屏 ≥1024px 右侧快捷栏：用户卡/在借件数/快捷入口，麦克风占位按钮）；物料列表/详情/借用弹窗/记录/结果/卡片页令牌化重做 + `MaterialImage.vue` 挂图（`/images/materials/{id}.png`，破图降级占位块）；管理端 63 处写死值令牌化。桌面宽屏+375px 手机双档 Playwright 全流程走查通过（intro/对话/BOM预约/安全确认/归还心得/超期审核/批量借出/录入物料）（commits `14faa67`/`99b119f`/`0933b16`/`a737f97`/`7216245` 起）
- [x] UI/UX 第二轮（按队长反馈强化）：taste-skill/redesign-skill 项目级安装进 `.kimi-code/skills/`（新会话可直接 `/skill:` 调用）；引入 gsap 3.15；开屏重做 **scrollytelling 滚动叙事页**（GSAP ScrollTrigger scrub 五屏：hero→物料流转→知识随行→经验闭环→能力卡进入屏，HUD 编号+右侧进度轨+图片视差，规范文档第 8 节补"开屏豁免条款"）；主界面浅色仪器感强化（蓝图网格底纹、卡片四角仪器角标、mono 功能标注 LOC/QA/ID/CARDS、分段控件 tabs、输入栏 `›` 控制台化、库存/在借读数化）。物料照片说明：当前是 Seedream 纯文生图（按真品外观描述），非基于真实产品图；要换真图直接同名覆盖 `frontend/public/images/materials/`（commits `47969b7`/`4fe95e2`/`1534507`）
- [x] 主界面第三轮（控制台化重构）：首页改为三栏控制台——左轨能力矩阵（C1-C4 机制行点击发送演示提问）+ 系统状态读数（物料登记/可借/会话/秒级时钟），中央对话控制台（在线 LED 头、纯 CSS 雷达徽标欢迎区、01-04 指令行、终端日志风过程显化、provenance 改 mono 状态点、输入框聚焦辉光），右轨用户读数 + 物料精选（真图真库存状态点）+ 快捷功能；<1024px 单列侧轨沉底；新增 `--lx-green-glow*` 令牌，规范文档第 10 节登记红线豁免（环境状态动画/mono 标号/唯一 eyebrow，待队长复核）；桌面+375px Playwright 走查通过（截图存 `deta/shots/`）
- [x] 登录认证：users 表加 `password_hash`/`role`（sha256+固定盐，演示级，见 `db.hash_password`），`POST /api/auth/login`（失败统一 1008 防枚举，API.md 第 9.1 节）；前端 `/login` 登录页 + 路由全局守卫（未登录→/login；student 挡 /admin；已登录访问 /login 按 role 分流）+ 顶栏用户名/role 徽标/退出（原账号切换 select 移除，管理 tab 仅 admin 可见）+ 开屏收尾未登录落 /login + 管理台侧栏"退出登录"；种子账号：学生 2024001 小王/2024002 小李（123456）、管理员 admin（admin888）
- [x] 前端第四轮升级（浅色未来感细化 + 交互重排，commit `a2d3555`）：主按钮内收角标+辉光、输入聚焦扫描线、路由过渡、激活 tab 强化；物料列表即时搜索+分类 chips+等级徽标（BASIC/ADV/PRO）+骨架屏；详情页主次按钮 2:1 层级；借期场景预设（课程设计/竞赛项目/长期研究）；物料精选在库优先+换一批；1024-1279 左轨修复（不再整条隐藏）；对话引用标签可点下钻卡片；管理台侧栏 01-05 序号+批量借出筛选+空态引导；`vite.config.js` watch 改轮询防 Windows EBUSY 崩溃；设计规范第 11 节登记；1440/1024/375 三视口截图 + vision 视觉回归通过（截图存 `deta/shots/redesign-*`，未入库）
- [x] 前端第五轮（可选五项全做，commit 见本轮提交记录）：深色主题一键切换（`labx_theme` 持久化+跟随系统+Element 深色映射）；<768px 底部 tab 栏（safe-area 适配）；记录页状态筛选胶囊；语音输入（Web Speech API 特性检测+降级提示）；对话 ghost 常用提问 chips；修复第四轮路由过渡导致的切换空白（回退无过渡，commit `a556f2c`）；规范文档第 12 节登记
- [x] 前端第六轮（commit `fd19a40`）：①去英文翻译标注——tabs/移动tab/等级徽标/LOC/CARDS/SYS/USER/ID/NAV/SCENE 等全中文化（保留 LABX 品牌与物料真名，C1-C4 与 01-04 编号保留）；②对话持久化——新增 `chatStore.js`（按账号 localStorage 分存），跨页面/刷新/重登不丢，控制台头「新会话」按钮 + 右轨「对话历史」列表切换；③暗黑模式黑白化——中性近黑灰阶+近白文字（页底 #0a0a0b/正文 #f4f4f5），绿仅点睛（#34c98e），Element 深色映射同步重写；规范文档第 13 节登记；浏览器截图 + vision 评审通过
- [x] 前端第七轮（开屏浅色化 + harness 风格控制台化，本次会话）：仿 deepseek.com/harness 动画风格重做开屏——去掉强制深色、跟随应用主题（默认浅色即浅色开屏）；首屏新增终端卡片（macOS 三圆点用语义色 danger/warning/success + 绿色 `$` 前缀 mono 命令，仿 harness 首屏"左文右终端"，≥1024px 并排）；背景三层：蓝图网格（复用 --lx-grid-line）→ 软绿流动波纹（--lx-green-glow-soft，reduced-motion 关闭）→ 点阵粒子 canvas（读当前主题 --lx-green，比旧星座更静）；seedream 5.0 Pro 重新生成 4 张浅色科技风开屏图（hero/scene1-3，暖白底+绿强调）；规范文档 §2.2 改述、§8 豁免条款扩展（终端卡片属红线 11 例外，**待队长复核**）、§14 登记；桌面 1440×900 逐屏 + 375px 移动 Playwright 走查 + vision 评审通过（截图存 `deta/shots/intro-light-*`，未入库）
- [x] 前端第八轮（开屏 1:1 仿 deepseek.com/harness 首屏动画）：开屏改为单屏自动播放，固定深色暗场（组件局部 data-theme=dark，应用主题不受影响）；背景三层对齐原站——软绿光晕漂移 + Seedream 5.0 Pro 生成 hero-dark.png（黑底荧光绿抽象X+粒子轨道，screen 混合、9s 呼吸、鼠标视差）+ 90px 规则点阵 canvas（30fps、鼠标140px斥力、静止自动停帧）；内容四块复刻 ds-hero-enter（opacity+translateY+blur 依次入场，视觉图 1.8s blur(20px)→0）；右栏终端 tab 切换（快速开始/能力清单）+ 复制按钮 + mono 绿色 `$` 前缀；保留跳过/Esc/未登录落 /login/reduced-motion 降级；规范文档 §8 豁免扩展、§15 登记；`npm run build` + Playwright 1440×900/375×667 实测通过（截图存 `deta/shots/intro-harness-*`，未入库）
- [x] 前端第九轮（开屏每次登录播放）：按队长要求移除 labx_intro_seen 仅首次标记——IntroOverlay 初始不播，watch(currentUser.role) 空→非空（登录成功）时 replay 整段开屏；App.vue 取消 /admin 排除（学生/管理员登录都播）；重播时重置终端tab/复制态/图片加载态/点阵状态，nextTick 后再起 canvas；已登录刷新不重播；规范文档 §16 登记；Playwright 实测学生登录/管理员登录/跳过/刷新不重播全通过（截图存 `deta/shots/intro-every-login-student.png`，未入库）
- [x] 前端第十轮（多屏开屏 + 登录前播放 + 学生向文案）：按队长三点反馈重做——开屏改 6 屏滚动叙事（hero + 为什么LabX + 物料流转 + 知识随行 + 智能助手 + 登录CTA），IntersectionObserver 滚入淡入 + 6节点进度轨，首屏副按钮"往下看"；播放时机改登录前（未登录进入即播、结束落 /login，sessionStorage 防同标签页重复、登出清除标记重播）；删除 npm/uvicorn/labx@console/GitHub 等开发者向内容，终端改学生动线与一句话能力；Seedream 5.0 Pro 新增 scene-dark-1/2/3 三张暗场绿色调场景图；规范文档 §8 豁免更新、§17 登记；`npm run build` + Playwright 1440×900/375×667 实测通过（截图存 `deta/shots/intro-multipage-*`，未入库）
- [x] 收尾轮（智能助手逻辑加固 + MCP 收敛 + 演示准备）：①orchestrator 物料提及清洗（去"我的/这个/那块"前缀）、跨轮次上下文（"那怎么接线"沿用上一轮物料）、本地检索严格型号对应（目标物料无卡片不再拿其他物料凑数）、逃生项诚实披露信息缺口、DuckDuckGo 检索词压 80 字、markdown 引用优先提取、纯打招呼/自我介绍固定快回；②db.py 新增 session_scope，MCP 三 server 统一上下文管理并复用 services.material_to_dict；③services 权限历史只算 active/returned（驳回申请不再算"借过"）；④`deta/experiences.csv` 5 条预置社区经验 + init_db 灌入（借 DHT22 推送首位即"前一位同学提醒"）；⑤新增 `scripts/start_demo.sh/.bat` 一键启动与 `scripts/preflight.py` 展示前自检；⑥AskPage 右轨管理台仅管理员可见 + 去残留英文 USER；⑦`docs/agent-workflow.md` 收尾修订登记；⑧`deta/checklist.md` 最终展示清单。实际 LLM 回归：你好/你能做什么/库存/1+1/排障澄清/BOM/跨轮次跟进全通过，preflight 全 PASS，UI Playwright 无报错
- [x] 多模态升级 + 资料上传闭环：①LLM 模型改 `deepseek-v4-flash-vision-exp`，`llm.chat_with_image` 走 OpenAI vision 消息格式（复用重试/MOCK 兜底）；②新增 `file_parser.py`（图片 base64 / PDF pypdf / Word python-docx / TXT 直读，10MB 上限）；③db 新增 `Upload` 表（pending/approved/rejected），`backend/uploads/` 存文件（已 gitignore）；④接口 `POST /api/uploads`（multipart）、`GET /api/uploads`、`POST /api/uploads/{id}/review`，错误码 1009 登记 API.md 第 11 节；⑤审核通过自动生成 `KC-UPLOAD-xxxx` tip 卡片并 `rag.add_card` 同步向量库；⑥新增第四个 MCP Server `file_server.py`（file-mcp，5 工具：解析/待审列表/详情/通过入库/驳回）；⑦orchestrator 全链路支持 `file_context`——图片跳检索阶梯直走 vision，文本截断 1500 字注入问答；⑧前端：AskPage 输入栏左侧回形针上传按钮（预览条+附件气泡）、物料详情页"确认借用/上传资料/问问AI"三按钮+上传弹窗、管理台侧栏"06 资料审核"（pending 角标+通过/驳回+驳回理由弹窗）；⑨上传与审核通过均返回鼓励文案。后端 Python requests 实测上传/审核/入卡全链路通过，Playwright 验证三端 UI（截图存 `deta/shots/`，未入库）
- [ ] 阶段 4：演示数据灌满 + 全流程测试 + 部署固化 + 录视频 ← **当前在这里**

**阶段 4 待办细节**（做完划掉）：
1. ~~物料照片：Seedream 批量生成~~ ✅ 已完成（15 张物料图 + 4 张开屏视觉，存 `deta/images/` 并拷 `frontend/public/`，前端已挂图；生成脚本 `backend/scripts/seedream_gen.py`/`seedream_batch.py`，教训：请求体必须加 `output_format:"png"` 否则默认返回 JPEG）
2. 3 个往期项目（含 BOM、心得、照片）~~+ 5 条预置社区经验~~ ✅ 5 条经验已完成（`deta/experiences.csv`，init_db 自动灌入）；3 个往期项目仍待补
3. 故障博物馆：烧坏的 Arduino 实物 + 手写"死因卡"（线下道具，队长/队员准备）
4. 全流程测试 checklist：✅ 清单已存 `deta/checklist.md`；真机走三遍（借还、问答、BOM、排障、归还、换账号）待执行
5. 部署固化：一台笔记本跑全部服务 + 启动脚本 ✅（`scripts/start_demo.sh` / `start_demo.bat` / `preflight.py`）；断网演示预案（`LABX_LLM_MOCK=true`）已具
6. 录制完整演示视频（防现场翻车）+ 5 分钟剧本排练
7. ~~前端美化~~ ✅ 已由"UI/UX 重构"完成（设计系统、大屏双栏适配、开屏动效、消息动效）；语音输入留到后续（输入栏已留麦克风占位按钮）
