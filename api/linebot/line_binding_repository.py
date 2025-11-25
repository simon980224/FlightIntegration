# api.linebot.line_binding_repository
# LINE 綁定服務（MSSQL / pymssql）
# - 使用 User.User_LineId 欄位進行綁定
# - 提供查詢與更新 User.User_LineId 的方法

import pymssql
from typing import Optional
from datetime import datetime

# 與 ticket_service 共用相同 DB 設定
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}


def get_user_id_by_line(line_user_id: str) -> Optional[str]:
    """用 LINE user_id 查綁定的網站 User_Id；查不到回 None"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute("SELECT User_Id FROM [User] WHERE User_LineId = %s", (line_user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()


def bind_line_user(user_id: str, line_user_id: str) -> dict:
    """建立或更新綁定：更新 User.User_LineId 欄位

    確保一對一關係：
    - 先檢查該 LINE ID 是否已被其他帳號綁定
    - 更新指定 User_Id 的 User_LineId 欄位

    回傳 {success: bool, error?: str, message?: str}
    """
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()

        # 檢查該 LINE ID 是否已被其他帳號綁定
        cursor.execute(
            "SELECT User_Id FROM [User] WHERE User_LineId = %s AND User_Id != %s",
            (line_user_id, user_id)
        )
        existing = cursor.fetchone()
        if existing:
            return {
                "success": False,
                "error": "此 LINE 帳號已綁定其他使用者",
                "message": "此 LINE 帳號已綁定其他使用者，請先解除綁定"
            }

        # 更新 User.User_LineId
        cursor.execute(
            "UPDATE [User] SET User_LineId = %s, Modify_At = GETDATE() WHERE User_Id = %s",
            (line_user_id, user_id)
        )

        if cursor.rowcount == 0:
            return {
                "success": False,
                "error": "使用者不存在",
                "message": "找不到該使用者"
            }

        conn.commit()
        return {"success": True, "message": "綁定成功"}

    except Exception as e:
        try:
            if conn: conn.rollback()
        finally:
            return {"success": False, "error": str(e)}
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()


def unbind_by_user(user_id: str) -> dict:
    """依網站 User_Id 解除綁定（將 User_LineId 設為 NULL）"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE [User] SET User_LineId = NULL, Modify_At = GETDATE() WHERE User_Id = %s",
            (user_id,)
        )
        conn.commit()
        return {"success": True, "message": "解除綁定成功"}
    except Exception as e:
        try:
            if conn: conn.rollback()
        finally:
            return {"success": False, "error": str(e)}
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()


def unbind_by_line(line_user_id: str) -> dict:
    """依 LINE user_id 解除綁定（將 User_LineId 設為 NULL）"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE [User] SET User_LineId = NULL, Modify_At = GETDATE() WHERE User_LineId = %s",
            (line_user_id,)
        )
        conn.commit()
        return {"success": True, "message": "解除綁定成功"}
    except Exception as e:
        try:
            if conn: conn.rollback()
        finally:
            return {"success": False, "error": str(e)}
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()

