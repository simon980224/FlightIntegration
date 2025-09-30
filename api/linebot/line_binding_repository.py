# api.linebot.line_binding_service
# 簡單的 LINE 綁定服務（MSSQL / pymssql）
# - 提供查詢與寫入 LineUserBinding 的方法
# - 避免重複綁定：插入前會先移除相同 User_Id 或相同 Line_User_Id 的舊綁定

import pymssql
from typing import Optional
from datetime import datetime

# 與 ticket_service 共用相同 DB 設定（為了快速落地，先重複一次；可抽成共用設定檔）
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

TABLE = "dbo.LineUserBinding"


def get_user_id_by_line(line_user_id: str) -> Optional[str]:
    """用 LINE user_id 查綁定的網站 User_Id；查不到回 None"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute(f"SELECT User_Id FROM {TABLE} WHERE Line_User_Id = %s", (line_user_id,))
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
    """建立或更新綁定：同一 User_Id 或同一 Line_User_Id 的舊綁定會被移除後再插入。
    以確保一對一。
    回傳 {success: bool, error?: str}
    """
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        # 先移除同帳號或同 LINE 的舊綁定
        cursor.execute(f"DELETE FROM {TABLE} WHERE User_Id = %s OR Line_User_Id = %s", (user_id, line_user_id))
        # 新增
        cursor.execute(
            f"INSERT INTO {TABLE} (User_Id, Line_User_Id, Created_At) VALUES (%s, %s, GETDATE())",
            (user_id, line_user_id)
        )
        conn.commit()
        return {"success": True}
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
    """依網站 User_Id 解除綁定"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE User_Id = %s", (user_id,))
        conn.commit()
        return {"success": True}
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
    """依 LINE user_id 解除綁定"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {TABLE} WHERE Line_User_Id = %s", (line_user_id,))
        conn.commit()
        return {"success": True}
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

