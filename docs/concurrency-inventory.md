# LabX 库存并发安全治理

> 记录 borrow / review / return 三个写路径从"读-改-写"改为"原子条件更新 + 短事务"的原因与原理。
> 对应提交：`dc33e21`（阶段5）。相关代码：`backend/services.py`、`backend/db.py`。

---

## 1. 问题：旧方案为什么会超卖

### 1.1 旧实现：先读，再在 Python 里改，最后 commit

旧 `borrow_core` 的库存处理是典型的 **读-改-写（read-modify-write）**：

```python
m = db.get(Material, material_id)          # ① 读库存
if m.available_quantity < quantity:        # ② 在 Python 里判断
    return 库存不足
m.available_quantity -= quantity           # ③ 在 Python 里修改
db.commit()                                # ④ 提交
```

归还、审核通过、物料编号生成也是同样的模式：先 `db.get()` 读出对象，改属性，再 `commit()`。

### 1.2 并发下的时序：两个请求都"看到"库存充足

假设某物料库存 `available = 1`，两个请求同时借 1 件：

```text
时刻   请求A                          请求B
t1    读到 available=1
t2                                 读到 available=1
t3    判断 1>=1 通过（Python 里）
t4                                 判断 1>=1 通过（Python 里）
t5    减为 0，commit
t6                                 减为 0，commit
结果  借出成功                      借出成功   → 实际借出 2 件，库存却只剩 1
```

两个请求在各自事务里读到的都是 `1`，判断都通过，各自 `UPDATE available=0`。第二次 UPDATE 会覆盖第一次（后写胜出），但**两条借用记录都插入了**。这就是超卖：

- 库存为 0，却产生了 2 条 active 借用记录；
- 后续归还时库存会被回补两次，变成 `2`，**凭空多出库存**。

同理还有几类并发缺陷：

| 场景 | 旧逻辑漏洞 |
|---|---|
| 重复归还 | 两个请求都读到 `status=active`，各自回补一次库存 → 库存翻倍 |
| 重复审批 | 两个管理员都读到 `pending`，各自扣库存 → 库存被扣两次 |
| 物料编号 | 两个请求都扫描出"最大序号 N"，都生成 `前缀-(N+1)` → 主键冲突或覆盖 |
| 借用记录编号 | `R-(1001+COUNT(*))`，两个请求 COUNT 相同 → 编号相同，主键冲突 |

### 1.3 根因

> **判断依据（读到的库存）和最终写入之间没有原子性保证。**

读和写是两个独立的 SQL，中间隔着 Python 代码和其他请求的事务。在单线程演示时不会出错，一旦多请求并发（多线程、多 worker、多实例），竞态窗口就会被打中。

---

## 2. 思路：把"判断"下沉到 SQL 的 WHERE 里

核心原则只有一条：

> **不要在 Python 里先读再判断；让数据库在同一条 SQL 里"边判断边改"。**

把"库存足够才扣"写进 UPDATE 的 WHERE 子句：

```sql
UPDATE materials
SET available_quantity = available_quantity - :qty
WHERE id = :mid AND available_quantity >= :qty;
```

数据库在执行这条 UPDATE 时会先锁定目标行、再检查条件、再写入——这三步在**同一条语句内是原子的**，其他事务插不进来。

- 库存够 → 命中 1 行，`rowcount=1`，扣减成功；
- 库存不够 → 条件不满足，命中 0 行，`rowcount=0`，什么都不改。

`rowcount` 就是"判断+扣减"的合并结果，Python 只需要看命中了几行，**不存在读到旧值的可能**。

并发时第二个请求执行到这条 UPDATE 时，第一个请求已经把库存扣掉了，它看到的条件是扣减后的值，自然命中 0 行返回库存不足。

---

## 3. 新方案的具体设计

### 3.1 库存扣减：原子条件 UPDATE

```python
def _atomic_decrement_stock(db, material_id, quantity) -> bool:
    res = db.execute(
        update(Material)
        .where(Material.id == material_id,
               Material.available_quantity >= quantity)   # 判断条件在 WHERE 里
        .values(available_quantity=Material.available_quantity - quantity)
    )
    return res.rowcount == 1   # 命中1行=扣成功，0行=库存不足/物料不存在
```

库存回补同理，但加一个上限保护，防止归还把库存加到超过总量：

```sql
UPDATE materials
SET available_quantity = available_quantity + :qty
WHERE id = :mid AND available_quantity + :qty <= total_quantity;
```

### 3.2 状态迁移：原子"认领"，防止重复操作

归还、审核的本质是"状态从 X 变为 Y，且只能变一次"。同样用条件 UPDATE 把"当前状态正确"写进 WHERE：

```sql
-- 归还：只有 active 能被改成 returned
UPDATE borrow_records
SET status='returned', returned_at=:now
WHERE id=:rid AND status='active';

-- 审核通过：只有 pending 能被改成 active
UPDATE borrow_records
SET status='active', review_status='approved', ...
WHERE id=:rid AND status='pending';
```

`rowcount==1` 表示本请求抢到了这次状态变更；并发下只有一个请求能命中，其余 `rowcount==0`，返回"该记录已处理"。**库存的扣/补只在抢到状态变更的那个请求里执行一次。**

### 3.3 短事务 + BEGIN IMMEDIATE

原子 UPDATE 解决了单条语句的竞态，但"扣库存 + 插借用记录"是**两条**语句，必须包在一个事务里，否则可能出现"库存扣了但记录没插"。

SQLite 默认是 deferred 事务（第一次写才取锁）。为了让"扣库存→插记录"这一组操作在并发下排队执行，进入写事务时立即取 RESERVED 锁：

```python
db.execute(text("BEGIN IMMEDIATE"))
# ... 原子 UPDATE 扣库存 ...
# ... INSERT 借用记录 ...
db.commit()   # 任一步失败 → rollback，不留半状态
```

效果：同一时刻只有一个请求能持有写锁走完这组操作，其余在锁上等待（配合 `busy_timeout`），天然串行化，杜绝写-写竞态。

事务必须**短**——锁持有期间不能调用 LLM、网络搜索、Chroma 等耗时操作。所以 AI 心得草稿、知识卡片推送都放在 `commit()` 之后执行，失败也不回滚已成功的归还。

### 3.4 记录编号：UUID，去掉"先数再编"

旧方案 `R-(1001+COUNT(*))` 需要一次数据库读取，两个并发请求 COUNT 相同就会撞号。改为：

```python
record_id = f"R-{uuid.uuid4().hex}"
```

不读库、不依赖全局计数，多进程/多实例也不会冲突，主键约束仅作兜底。

### 3.5 物料编号：序列表原子取号

物料编号要保留人类可读的 `A-017`、`S-010` 形式，不能用 UUID，所以单独建一张序列表：

```sql
CREATE TABLE material_sequences (
    prefix TEXT PRIMARY KEY,   -- A/S/M/T/H/E
    next_seq INTEGER NOT NULL
);
```

取号用原子 `UPDATE ... RETURNING`，先自增再取回旧值：

```sql
UPDATE material_sequences SET next_seq = next_seq + 1
WHERE prefix = :prefix RETURNING next_seq;
```

`RETURNING` 返回的是自增后的值，减 1 即本次分配到的序号。整个"取号"在一条 UPDATE 内完成，并发下不会有两个请求拿到同一个序号。替代了旧的"扫描同前缀最大序号 + 1"（那是读-改-写，会撞号）。

### 3.6 数据库约束：最后一道防线

即使应用层全部失守，数据库也要兜住：

- **部分唯一索引**：同一用户同一物料最多一条未完成借用

  ```sql
  CREATE UNIQUE INDEX uq_borrow_open_user_material
  ON borrow_records(user_id, material_id)
  WHERE status IN ('active','pending');
  ```

  应用层"先查是否已借"的检查可被并发穿透，这个索引保证数据库层面也插不进第二条，捕获 `IntegrityError` 返回 `1005`。

- **CHECK 约束**：`available >= 0`、`available <= total`、`quantity > 0`、状态枚举值合法。
- **外键**：`borrow_records.user_id → users.id`、`material_id → materials.id`，杜绝孤儿记录。

约束不能替代事务，但能阻止任何漏网代码写入非法数据。

### 3.7 SQLite 连接配置

```sql
PRAGMA journal_mode = WAL;      -- 读写不互斥，提升并发读
PRAGMA foreign_keys = ON;       -- 真正启用外键
PRAGMA busy_timeout = 5000;     -- 写锁被占时等待5秒而非立刻报错
```

注意：**WAL 提升的是读写并发，SQLite 仍是单写者模型**。写正确性靠的是上面的原子 UPDATE + 短事务，WAL 只是让等待更平滑。若未来要多实例/高写入，应迁移 PostgreSQL——原子 UPDATE 和约束设计可以直接沿用。

---

## 4. 事务边界一览

| 操作 | 事务内（持写锁） | 事务外（提交后） |
|---|---|---|
| 借用 | 原子扣库存 + 插 active 记录 | 推送知识卡片 |
| 审核通过 | 认领 pending→active + 原子扣库存 | 推送知识卡片 |
| 归还 | 认领 active→returned + 原子回补库存 | 生成 AI 心得草稿 |
| 录入物料 | 序列表取号 + 插物料 | — |

错误码：库存不足 `1001`、重复借用 `1005`、状态非法 `1004`、锁冲突可重试 `1010`、库存回补异常 `1011`。

---

## 5. 验证

真实 SQLite 磁盘库、每线程独立 Session，并发测试 **17/17 通过**：

| 场景 | 断言 | 结果 |
|---|---|---|
| 库存竞争（60人抢10件） | 恰10成功、50库存不足、库存归零非负、记录ID唯一 | PASS |
| 重复归还（30并发） | 仅1成功、库存只回补1次 | PASS |
| 重复审批（20并发） | 仅1成功、库存只扣1次 | PASS |
| 重复借用（20并发） | 仅1条未完成记录、唯一索引拦截 | PASS |
| 并发录入（50并发） | 全部成功、编号唯一 | PASS |

API 全链路回归 **20/20 通过**（正常借还、驳回拦截归还、审核借出、录入、同名/重复借用拦截）。

---

## 6. 小结

| | 旧方案 | 新方案 |
|---|---|---|
| 库存 | Python 读-改-写，竞态超卖 | 原子条件 UPDATE，判断下沉到 WHERE |
| 状态迁移 | 先读状态再改，可被并发重复执行 | 条件 UPDATE 原子认领，只生效一次 |
| 多步操作 | 无明确事务边界 | BEGIN IMMEDIATE 短事务，失败回滚 |
| 借用记录号 | COUNT 扫描，并发撞号 | UUID，零冲突 |
| 物料编号 | 扫描最大序号+1，并发撞号 | 序列表原子取号 |
| 兜底 | 无约束 | 部分唯一索引 + CHECK + 外键 |
