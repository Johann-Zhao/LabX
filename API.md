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
入参: { "user_id": "2024001", "material_id": "A-017", "safety_confirmed": false }
返回: { "code": 0, "msg": "借用成功",
       "data": { "record_id": "R-1024", "material_id": "A-017", "status": "active",
                 "borrowed_at": "2026-08-11T20:30:00", "due_at": "2026-08-25T20:30:00",
                 "knowledge_card": { "card_id": "KC-S003-ERR", "title": "DHT22 最易错点",
                                     "points": ["最易错点...", "关联物料...", "深入入口..."],
                                     "link": "/materials/S-003" } } }
```

说明：
- `safety_confirmed`：进阶级物料首次借用时，前端弹一屏安全要点，学生勾选"我已知晓"后置 `true` 重新提交。
- 进阶级未确认 → `code: 1002`，`data.safety_notice` 为安全要点文案；专业级 → `code: 1003`。
- 借用成功后 `knowledge_card` 为借用触发推送的单张知识卡片（三要点结构）；无卡片时该字段为 `null`。

## 4. 归还

```
POST /api/return
入参: { "record_id": "R-1024" }
返回: { "code": 0, "msg": "归还成功",
       "data": { "record_id": "R-1024", "status": "returned",
                 "returned_at": "2026-08-11T21:00:00",
                 "experience_draft": "这次用 DHT22 测温室数据比较顺利，提醒大家：数据脚一定记得接上拉电阻……" } }
```

说明：`experience_draft` 为 AI 预填的心得草稿，前端弹出供学生修改或确认后调 `POST /api/experience` 发布（非强制）。

## 5. 借用流水

```
GET /api/records?user_id=
入参: user_id（可选；为空返回全部，供管理员视角）
返回: { "code": 0, "msg": "ok",
       "data": [ { "record_id": "R-1024", "user_id": "2024001", "material_id": "S-003",
                   "material_name": "DHT22 温湿度传感器", "status": "active",
                   "borrowed_at": "2026-08-11T20:30:00", "due_at": "2026-08-25T20:30:00",
                   "returned_at": null } ] }
```

`status` 取值：`pending`（待审批）/ `active`（借用中）/ `overdue`（逾期）/ `returned`（已归还）。

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
       "data": { "project_guess": "土壤湿度监测 + 水泵控制的自动浇花装置",
                 "materials": [ { "material_id": "A-017", "name": "Arduino Uno 开发板",
                                  "available_quantity": 3, "in_stock": true } ],
                 "skills": [ { "name": "Arduino 基础编程", "link": "/materials/A-017" } ],
                 "reference_projects": [ { "project_id": "P-2025-06",
                                           "title": "张XX的自动浇花系统（2025年6月）" } ] } }
```

说明：推荐物料经过库存即时校验，`in_stock: false` 的物料前端置灰提示"缺货，可加入等待队列"。一键预约由前端对 `in_stock` 物料逐个调 `POST /api/borrow` 实现。

## 8. 提交使用经验

```
POST /api/experience
入参: { "material_id": "S-003", "user_id": "2024001",
        "content": "数据脚一定要接上拉电阻，我开始忘了接，读数一直是 0。",
        "record_id": "R-1024" }
返回: { "code": 0, "msg": "经验已提交，感谢分享",
       "data": { "tip_id": "TIP-0042",
                 "structured": { "problem": "DHT22 读数一直是 0",
                                 "solution": "数据脚接 4.7kΩ 上拉电阻到 VCC",
                                 "scenario": "DHT22 首次接线、温湿度数据采集项目" } } }
```

说明：`structured` 为 LLM 结构化结果（问题/解决方案/适用场景），入库后参与半衰期降权与"有用"投票。`record_id` 可选，归还流程带入。

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
| 1005 | 你已借出该物料（重复借用） |

> 阶段 0 假接口只会返回 0 / 404 / 1002 / 1003；1001 / 1004 / 1005 为阶段 1 真实状态机预留。
