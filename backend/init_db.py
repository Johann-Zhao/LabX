"""初始化数据库：建表 + 灌入演示数据。可重复跑（每次先清库重建）。

用法（Git Bash，在 backend/ 目录、venv 激活后）：
    python init_db.py

物料数据来源（二选一）：
1. ../deta/materials.csv 存在 → 从 CSV 导入（成员 C 维护）
2. 否则 → 写入 3 条内置样例物料

CSV 格式（UTF-8 保存，第一行表头，Excel 另存为 CSV 即可）：
material_id,name,model,category,access_level,total_quantity,available_quantity,location,description

测试用户始终写入：2024001 小王、2024002 小李（演示"换个账号"用）。
"""
import csv
import os
from datetime import datetime

from db import Base, BorrowRecord, Material, SessionLocal, User, engine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "deta", "materials.csv")

SAMPLE_MATERIALS = [
    {
        "id": "A-017", "name": "Arduino Uno 开发板", "model": "Uno R3",
        "category": "开发板", "access_level": "advanced",
        "total_quantity": 5, "available_quantity": 5,
        "location": "201室 A柜", "description": "入门首选单片机开发板，适合绝大多数创意原型项目。",
    },
    {
        "id": "S-003", "name": "DHT22 温湿度传感器", "model": "DHT22 / AM2302",
        "category": "传感器", "access_level": "basic",
        "total_quantity": 10, "available_quantity": 10,
        "location": "201室 B柜", "description": "数字温湿度传感器，单总线通信，注意数据脚需上拉。",
    },
    {
        "id": "M-011", "name": "L298N 电机驱动模块", "model": "L298N 双H桥",
        "category": "驱动模块", "access_level": "advanced",
        "total_quantity": 4, "available_quantity": 4,
        "location": "201室 A柜", "description": "直流电机/步进电机驱动，逻辑电源与电机电源需分开供电。",
    },
]

SAMPLE_USERS = [
    {"id": "2024001", "name": "小王"},
    {"id": "2024002", "name": "小李"},
]


def load_materials() -> list[dict]:
    """优先读 C 维护的 CSV，没有则用内置样例。"""
    if os.path.exists(CSV_PATH):
        rows = []
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows.append({
                    "id": row["material_id"].strip(),
                    "name": row["name"].strip(),
                    "model": row.get("model", "").strip(),
                    "category": row["category"].strip(),
                    "access_level": row.get("access_level", "basic").strip() or "basic",
                    "total_quantity": int(row["total_quantity"]),
                    "available_quantity": int(row.get("available_quantity") or row["total_quantity"]),
                    "location": row["location"].strip(),
                    "description": row.get("description", "").strip(),
                })
        print(f"从 {os.path.abspath(CSV_PATH)} 导入 {len(rows)} 条物料")
        return rows
    print(f"未找到 {os.path.abspath(CSV_PATH)}，使用内置样例物料 {len(SAMPLE_MATERIALS)} 条")
    return SAMPLE_MATERIALS


def main() -> None:
    # 清库重建：演示数据随时可推倒重来
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        for u in SAMPLE_USERS:
            db.add(User(id=u["id"], name=u["name"], created_at=datetime.now()))
        for m in load_materials():
            db.add(Material(**m, created_at=datetime.now(), updated_at=datetime.now()))
        db.commit()
    finally:
        db.close()

    # 打印结果，方便人工核对
    db = SessionLocal()
    try:
        print(f"users: {[u.id + ' ' + u.name for u in db.query(User).all()]}")
        for m in db.query(Material).all():
            print(f"  {m.id} {m.name} [{m.category}/{m.access_level}] 库存 {m.available_quantity}/{m.total_quantity} @ {m.location}")
        print(f"borrow_records: {db.query(BorrowRecord).count()} 条（应为 0）")
    finally:
        db.close()
    print("初始化完成 →", os.path.join(BASE_DIR, "labx.db"))


if __name__ == "__main__":
    main()
