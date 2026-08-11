"""数据库模型：按《LabX方案》附录 A 建表。

与附录 A 的差异（已在 AGENTS.md 第 9 节登记）：
- materials 增加 description 字段（一句用途说明，物料列表页要展示）
- borrow_records 去掉用不到的 borrow_type 字段；status 增加 pending（专业级待审批）
- users 表附录 A 未给结构，这里只保留最小字段（id=学号、姓名）
"""
import os
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "labx.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Material(Base):
    __tablename__ = "materials"

    id = Column(String(32), primary_key=True)  # 物料编号，如 A-017
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)  # 开发板/传感器/工具/耗材/设备
    model = Column(String(100))  # 型号规格
    location = Column(String(200), nullable=False)  # 存放位置（实验室+柜号）
    total_quantity = Column(Integer, nullable=False)
    available_quantity = Column(Integer, nullable=False)
    access_level = Column(String(20), nullable=False, default="basic")  # basic/advanced/professional
    description = Column(String(500))  # 一句用途说明
    safety_video_url = Column(String(500))  # 安全操作视频（专业级物料用，阶段 3）
    image_url = Column(String(500))
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class User(Base):
    __tablename__ = "users"

    id = Column(String(32), primary_key=True)  # 学号
    name = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)


class BorrowRecord(Base):
    __tablename__ = "borrow_records"

    id = Column(String(32), primary_key=True)  # 记录编号，R-1001 起递增
    user_id = Column(String(32), nullable=False)
    material_id = Column(String(32), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="active")  # pending/active/returned/rejected
    borrowed_at = Column(DateTime, nullable=False, default=datetime.now)
    due_at = Column(DateTime, nullable=False)
    returned_at = Column(DateTime)
    experience_shared = Column(Boolean, default=False)  # 归还时是否已分享心得
    # 超期借用分级审核（>30 天需人工审核）：approved 无需审核/已通过，pending 待审核，rejected 已驳回
    review_status = Column(String(20), nullable=False, default="approved")
    review_reason = Column(Text)  # 学生申请超期借用时填写的理由


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id = Column(String(64), primary_key=True)  # KC-<文件名>，如 KC-S-003-manual
    material_id = Column(String(32), nullable=False)  # 关联物料 ID
    card_type = Column(String(20), nullable=False)  # manual/quickstart/common_errors/tip
    title = Column(String(300), nullable=False)
    points = Column(Text, nullable=False, default="[]")  # 三条要点，JSON 数组字符串
    content = Column(Text)  # 正文 markdown
    source = Column(String(500))  # 资料来源网址（官方文档/数据手册/教程）
    media_urls = Column(Text)  # 关联图片/视频，JSON 数组字符串
    contributor_id = Column(String(32))  # 贡献者（社区经验 tip 用）
    helpful_count = Column(Integer, default=0)  # "有用"投票数
    created_at = Column(DateTime, nullable=False, default=datetime.now)


def display_status(record: "BorrowRecord") -> str:
    """逾期不落库，读取时动态判断：active 且已过应还时间 → overdue。"""
    if record.status == "active" and record.due_at < datetime.now():
        return "overdue"
    return record.status
