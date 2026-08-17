"""user-mcp：用户服务 MCP Server。

FastMCP 薄封装，权限与统计逻辑复用 services.py。
运行：python mcp_servers/user_server.py（stdio 传输）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP

from db import BorrowRecord, Material, User, session_scope
from services import check_permission_core, get_user_stats_core

mcp = FastMCP("user-mcp")


@mcp.tool()
def authenticate_user(student_id: str, auth_method: str = "student_id") -> dict:
    """用户认证（演示版：仅学号，不采生物特征，见 NFR3）。"""
    with session_scope() as db:
        u = db.get(User, student_id)
        if u is None:
            return {"code": 404, "msg": f"用户 {student_id} 不存在"}
        return {"code": 0, "msg": "认证成功", "user": {"user_id": u.id, "name": u.name}}


@mcp.tool()
def get_skill_passport(user_id: str) -> dict:
    """技能护照：按借用历史推导技能覆盖类别与等级（借过进阶级物料 → 进阶）。"""
    with session_scope() as db:
        stats = get_user_stats_core(db, user_id)
        if stats is None:
            return {"code": 404, "msg": f"用户 {user_id} 不存在"}
        rows = (
            db.query(Material.category, Material.access_level)
            .join(BorrowRecord, BorrowRecord.material_id == Material.id)
            .filter(BorrowRecord.user_id == user_id)
            .all()
        )
        categories = sorted({c for c, _ in rows})
        touched_advanced = any(lv in ("advanced", "professional") for _, lv in rows)
        return {
            "code": 0,
            "msg": "ok",
            "passport": {
                "user_id": user_id,
                "name": stats["name"],
                "level": "进阶" if touched_advanced else "新手",
                "borrowed_categories": categories,
                "total_borrows": stats["total_borrows"],
                "can_borrow": "professional 需审批" if touched_advanced else "basic/advanced",
            },
        }


@mcp.tool()
def check_borrow_permission(user_id: str, material_id: str) -> dict:
    """检查用户对指定物料的借用权限：ok / need_safety_confirm / need_approval。"""
    with session_scope() as db:
        return check_permission_core(db, user_id, material_id)


@mcp.tool()
def get_user_stats(user_id: str) -> dict:
    """用户借用统计与当前借用清单（编排引擎排障分支确认上下文用）。"""
    with session_scope() as db:
        stats = get_user_stats_core(db, user_id)
        if stats is None:
            return {"code": 404, "msg": f"用户 {user_id} 不存在"}
        return {"code": 0, "msg": "ok", "stats": stats}


if __name__ == "__main__":
    mcp.run()
