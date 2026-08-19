"""数据库模型：按《LabX方案》附录 A 建表。

与附录 A 的差异（已在 AGENTS.md 第 9 节登记）：
- materials 增加 description 字段（一句用途说明，物料列表页要展示）
- borrow_records 去掉用不到的 borrow_type 字段；status 增加 pending（专业级待审批）
- users 表附录 A 未给结构，这里按最小字段 + 登录认证（password_hash/role，API.md 第 9.1 节）
"""
import hashlib
import os
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index,
                        Integer, String, Text, create_engine, event, text)
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "labx.db")

# timeout=5：库被写锁占用时等待 5 秒再报 database is locked（busy_timeout 兜底）
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 5},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _record):
    """每个新连接启用 WAL（读写并发）、外键和 busy_timeout。

    SQLite 仍是单写者模型，并发正确性靠原子条件更新 + 短事务保证（见 services）。
    """
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.execute("PRAGMA foreign_keys = ON")
    cur.execute("PRAGMA busy_timeout = 5000")
    cur.close()


@contextmanager
def session_scope():
    """统一数据库会话上下文：MCP 工具/脚本与短生命周期逻辑共用，避免漏 close。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (
        CheckConstraint("total_quantity >= 0", name="ck_material_total_nonneg"),
        CheckConstraint("available_quantity >= 0", name="ck_material_avail_nonneg"),
        CheckConstraint("available_quantity <= total_quantity", name="ck_material_avail_lte_total"),
    )

    id = Column(String(32), primary_key=True)  # 物料编号，如 A-017
    name = Column(String(200), nullable=False, unique=True)  # 名称唯一，防并发录入同名物料
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

    id = Column(String(32), primary_key=True)  # 学号/账号
    name = Column(String(50), nullable=False)
    password_hash = Column(String(64))  # sha256 十六进制，见 hash_password
    role = Column(String(20), nullable=False, default="student")  # student/admin
    created_at = Column(DateTime, nullable=False, default=datetime.now)


def hash_password(user_id: str, password: str) -> str:
    """演示级口令哈希：sha256(学号 + 固定盐 + 密码)。课程演示够用；
    生产环境应换 bcrypt/argon2 并每人随机盐。"""
    return hashlib.sha256((user_id + ":labx:" + password).encode("utf-8")).hexdigest()


class BorrowRecord(Base):
    __tablename__ = "borrow_records"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_borrow_qty_positive"),
        CheckConstraint("status IN ('pending','active','returned','rejected')", name="ck_borrow_status"),
        CheckConstraint("review_status IN ('approved','pending','rejected')", name="ck_borrow_review_status"),
        # 部分唯一索引：同一用户对同一物料最多一条未完成记录（应用层检查的并发兜底）
        Index("uq_borrow_open_user_material", "user_id", "material_id",
              unique=True, sqlite_where=text("status IN ('active','pending')")),
    )

    id = Column(String(48), primary_key=True)  # 记录编号 R-<uuid32>，见 services.new_record_id
    user_id = Column(String(32), ForeignKey("users.id"), nullable=False)
    material_id = Column(String(32), ForeignKey("materials.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default="active")  # pending/active/returned/rejected
    borrowed_at = Column(DateTime, nullable=False, default=datetime.now)
    due_at = Column(DateTime, nullable=False)
    returned_at = Column(DateTime)
    experience_shared = Column(Boolean, default=False)  # 归还时是否已分享心得
    # 超期借用分级审核（>30 天需人工审核）：approved 无需审核/已通过，pending 待审核，rejected 已驳回
    review_status = Column(String(20), nullable=False, default="approved")
    review_reason = Column(Text)  # 学生申请超期借用时填写的理由


class MaterialSequence(Base):
    """物料编号序列表：按分类前缀原子取号，替代"扫描同前缀最大序号+1"（并发安全）。

    next_seq 是"下一个可用序号"，取号时原子 UPDATE ... RETURNING。
    """
    __tablename__ = "material_sequences"

    prefix = Column(String(8), primary_key=True)  # A/S/M/T/H/E，见 services.CATEGORY_PREFIX
    next_seq = Column(Integer, nullable=False, default=1)


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"

    id = Column(String(64), primary_key=True)  # KC-<文件名>，如 KC-S-003-manual
    material_id = Column(String(32), ForeignKey("materials.id"), nullable=False)  # 关联物料 ID
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
