# LabX 接口契约（API.md）

> 前后端唯一契约，由后端维护（成员 B）。**任何变更先在群里说一声再改代码。**
> 统一返回格式：`{ "code": 0, "msg": "...", "data": ... }` —— `code = 0` 表示成功，非 0 为业务错误码（见文末）。
> 时间字段均为 ISO 8601 字符串；开发阶段所有接口在 `backend/main.py` 有返回假数据的骨架，前端可直接对接。

---

## 0. 联调检查

```
GET /api/ping
返回: { "msg": "pong" }
```

## 1. 物料列表 + 搜索

```
GET /api/materials?keyword=&category=
入参: keyword（可选，模糊匹配名称/型号）、category（可选，精确匹配分类）
返回: { "code": 0, "msg": "ok",
       "data": [ { "material_id": "S-003", "name": "DHT22 温湿度传感器",
                   "model": "DHT22 / AM2302", "category": "传感器",
                   "access_level": "basic", "total_quantity": 10, "available_quantity": 8,
                   "location": "201室 B柜",
                   "description": "数字温湿度传感器，单总线通信，注意数据脚需上拉。" } ] }
```

`access_level` 取值：`basic`（基础级，直接借）/ `advanced`（进阶级，首次借用需安全确认）/ `professional`（专业级，需教师审批）。

## 2. 物料详情

```
GET /api/materials/{material_id}
返回: { "code": 0, "msg": "ok",
       "data": { "material_id": "S-003", "name": "DHT22 温湿度传感器", "model": "DHT22 / AM2302",
                 "category": "传感器", "access_level": "basic",
                 "total_quantity": 10, "available_quantity": 8, "location": "201室 B柜",
                 "description": "...",
                 "knowledge_cards": [ { "card_id": "KC-S003-ERR", "card_type": "common_errors",
                                        "title": "常见错误" } ],
                 "tips_count": 2 } }
```

`card_type` 取值：`manual`（说明书要点）/ `quickstart`（3 分钟上手）/ `common_errors`（常见错误）/ `tip`（社区经验）。

## 3. 借用

```
POST /api/borrow
入参: { "user_id": "2024001", "material_id": "A-017", "safety_confirmed": false,
        "days": 30, "reason": "" }
返回: { "code": 0, "msg": "借用成功",
       "data": { "record_id": "R-1024", "material_id": "A-017", "status": "active",
                 "review_status": "approved",
                 "borrowed_at": "2026-08-11T20:30:00", "due_at": "2026-09-10T20:30:00",
                 "knowledge_card": { "card_id": "KC-S003-ERR", "title": "DHT22 最易错点",
                                     "points": ["最易错点...", "关联物料...", "深入入口..."],
                                     "link": "/materials/S-003" } } }
```

说明：
- `safety_confirmed`：进阶级物料首次借用时，前端弹一屏安全要点，学生勾选"我已知晓"后置 `true` 重新提交（**已生效**）。
- 进阶级未确认 → `code: 1002`，`data.safety_notice` 为安全要点文案；专业级 → `code: 1003`。
- 重复借用（同一用户对该物料有未完结记录）→ `code: 1005`，`data.record_id` 为已有记录。
- `days`：借用天数，可选，默认 30，允许范围 1~180（超出自动截断）。**≤ 30 天直接借出**（`status=active, review_status=approved`）；**> 30 天需人工审核**：
  - 未填 `reason` → `code: 1006`（不产生记录）；
  - 填了 `reason` → 创建 `status=pending, review_status=pending` 的申请记录，**不扣库存、不算借用中**，`knowledge_card` 为 `null`，`msg` 为"已提交审核"。审核见第 3.1 节。
- 借用成功后 `knowledge_card` 为借用触发推送的单张知识卡片（三要点结构，取该物料的 common_errors 卡片）；该物料没有任何卡片时为 `null`。

## 3.1 借用审核（管理端）

```
POST /api/borrow/review
入参: { "record_id": "R-1024", "approve": true }
返回: { "code": 0, "msg": "已通过，物料借出",
       "data": { "record_id": "R-1024", "status": "active", "review_status": "approved",
                 "borrowed_at": "...", "due_at": "...",
                 "knowledge_card": { …同借用推送… } } }
```

说明：仅对 `status=pending` 的记录有效，其他状态 → `code: 1004`。通过：记录转 `active`、库存 -1，**借期自审核通过时刻起算**（天数 = 申请时的 days），并补推知识卡片；驳回：`status=rejected, review_status=rejected`，不扣库存。演示时不做管理端 UI，用 `/docs` 页面调用。

## 4. 归还

```
POST /api/return
入参: { "record_id": "R-1024" }
返回: { "code": 0, "msg": "归还成功",
       "data": { "record_id": "R-1024", "status": "returned",
                 "returned_at": "2026-08-11T21:00:00",
                 "experience_draft": "这次用 DHT22 测温室数据比较顺利，提醒大家：数据脚一定记得接上拉电阻……" } }
```

说明：`experience_draft` 为 AI 预填的心得草稿，前端弹出供学生修改或确认后调 `POST /api/experience` 发布（非强制）。LLM 不可用时为模板拼装文案，永不为 `null`。

## 5. 借用流水

```
GET /api/records?user_id=
入参: user_id（可选；为空返回全部，供管理员视角）
返回: { "code": 0, "msg": "ok",
       "data": [ { "record_id": "R-1024", "user_id": "2024001", "material_id": "S-003",
                   "material_name": "DHT22 温湿度传感器", "status": "active",
                   "review_status": "approved", "review_reason": null,
                   "borrowed_at": "2026-08-11T20:30:00", "due_at": "2026-09-10T20:30:00",
                   "returned_at": null } ] }
```

`status` 取值：`pending`（超期借用审核中）/ `active`（借用中）/ `overdue`（逾期）/ `returned`（已归还）/ `rejected`（审核驳回）。
`review_status` 取值：`approved`（无需审核或已通过）/ `pending`（等待人工审核）/ `rejected`（已驳回）；`review_reason` 为学生申请超期借用时填写的理由。

## 6. RAG 问答

```
POST /api/ask
入参: { "question": "DHT22 读数总是 0 怎么回事", "material_id": "S-003" }
返回: { "code": 0, "msg": "ok",
       "data": { "answer": "DHT22 读数一直是 0，最常见的原因是数据脚没接上拉电阻……",
                 "references": [ { "card_id": "KC-S003-ERR", "title": "DHT22 最易错点" } ] } }
```

说明：`material_id` 可选——在物料详情页（数字分身对话窗）提问时带上，限定该物料的知识上下文；开放式知识查询不传。LLM 不可达时返回兜底答案且不报错（`code` 仍为 0）。

## 7. 愿望到方案

```
POST /api/recommend_bom
入参: { "description": "我想做一个能自动浇花的装置", "user_id": "2024001" }
返回: { "code": 0, "msg": "ok",
       "data": { "feasible": true,
                 "project_guess": "土壤湿度监测 + 水泵控制的自动浇花装置",
                 "assumption": "按单盆花、5V 供电的基础款估算",
                 "plan": [ "1. 硬件：土壤湿度传感器接 A0，水泵经继电器接 D8",
                           "2. 代码：定时采样，湿度低于阈值开泵 3 秒",
                           "3. 调试：先串口看读数，再带载试水后整定阈值" ],
                 "materials": [ { "material_id": "A-017", "name": "Arduino Uno 开发板",
                                  "spec": "Uno R3", "quantity": 1, "purpose": "主控",
                                  "source": "lab", "available_quantity": 5, "in_stock": true },
                                { "material_id": null, "name": "硅胶水管",
                                  "spec": "内径 6mm，1 米", "quantity": 1, "purpose": "水路",
                                  "source": "buy", "available_quantity": 0, "in_stock": false } ],
                 "skills": [ { "name": "Arduino 基础编程", "link": "/materials/A-017" } ],
                 "reference_projects": [] } }
```

说明：
- LLM 按项目真实需要生成**全链路方案（plan，4-6 步）+ 完整物料清单（bom，不限于实验室目录）**，后端逐件与物料目录模糊匹配：命中 → `source=lab` 并带实时库存；未命中 → `source=buy`（`material_id` 为 `null`），表示需自行购买。`assumption` 为方案基于的默认配置假设。
- 项目明显超出高校创新空间能力（高危/需资质/成本过高，如造真赛车、火箭）时返回 `feasible: false`，此时只有 `reply` 字段（幽默回应 + 可落地的替代建议），其余字段为空。
- 一键预约由前端对 `source=lab 且 in_stock` 的物料逐个调 `POST /api/borrow` 实现（按 `quantity` 约对应件数，库存不足按现有库存约）。
- LLM 不可用时退回关键词匹配（`plan` 为空数组、`source` 全部为 `lab`），接口永远可用。

## 8. 提交使用经验

```
POST /api/experience
入参: { "material_id": "S-003", "user_id": "2024001",
        "content": "数据脚一定要接上拉电阻，我开始忘了接，读数一直是 0。",
        "record_id": "R-1024" }
返回: { "code": 0, "msg": "经验已提交，感谢分享",
       "data": { "tip_id": "KC-TIP-1042",
                 "structured": { "problem": "DHT22 读数一直是 0",
                                 "solution": "数据脚接 4.7kΩ 上拉电阻到 VCC",
                                 "scenario": "DHT22 首次接线、温湿度数据采集项目" } } }
```

说明：`structured` 为 LLM 结构化结果（问题/解决方案/适用场景，LLM 不可用时退回原文截取）。入库为 tip 卡片并同步向量库，下一次借用该物料时以"前一位同学提醒"出现在知识推送首位。`record_id` 可选，归还流程带入。

## 9. 用户列表

```
GET /api/users
返回: { "code": 0, "msg": "ok",
       "data": [ { "user_id": "2024001", "name": "小王" } ] }
```

## 10. 智能体对话

```
POST /api/agent/chat
入参: { "user_id": "2024001", "message": "我的电机不转" }
返回: { "code": 0, "msg": "ok",
       "data": { "intent": "troubleshoot",
                 "steps": [ { "step": "意图识别", "detail": "识别为「故障排查」" },
                            { "step": "确认借用上下文", "detail": "你当前借用：L298N 电机驱动模块" },
                            { "step": "检索故障知识库", "detail": "命中《L298N 最容易踩的三个坑》" },
                            { "step": "确认备件库存", "detail": "备件：L298N 当前可借 2 件，存放于 201室 A柜" } ],
                 "answer": "最可能原因：逻辑电源与电机电源没分开供电……",
                 "references": [ { "card_id": "KC-M-011-common_errors", "title": "L298N 最容易踩的三个坑" } ],
                 "bom": null } }
```

说明：`intent` 取值 `troubleshoot`（排障）/ `recommend`（求推荐，此时 `bom` 字段为第 7 节的 BOM 结构化数据；`feasible=false` 时 `bom` 为 `null`，`answer` 为幽默回应+替代建议）/ `inventory`（查库存）/ `chitchat`（走通用 RAG 问答）。`steps` 是编排引擎的中间调用过程，前端用于展示"多能力协作"。

## 11. 知识卡片全文

```
GET /api/cards/{card_id}
返回: { "code": 0, "msg": "ok",
       "data": { "card_id": "KC-S-003-common_errors", "material_id": "S-003",
                 "card_type": "common_errors", "title": "DHT22 最容易踩的三个坑",
                 "points": ["...", "...", "..."],
                 "content": "## 详细说明\n...（markdown 正文）",
                 "source": "https://learn.adafruit.com/dht",
                 "helpful_count": 0 } }
```

说明：卡片详情页（保姆级教程）的数据源；`source` 为卡片编写时参考的官方资料网址。

---

## 业务错误码

| code | 含义 |
|---|---|
| 0 | 成功 |
| 404 | 资源不存在（物料 / 记录） |
| 1001 | 库存不足 |
| 1002 | 进阶级物料首次借用，需安全确认（`data.safety_notice` 为要点文案） |
| 1003 | 专业级物料需教师审批 |
| 1004 | 记录不存在或当前状态不允许该操作 |
| 1005 | 你已借出该物料（重复借用；含审核中的申请） |
| 1006 | 借用超过 30 天需填写申请理由（`days > 30` 且 `reason` 为空） |

> 当前状态：全部接口为真实实现。1002 / 1003 权限拦截已生效（阶段 3）；超期借用分级审核（1006 + 第 3.1 节）已生效；智能体对话见第 10 节。
