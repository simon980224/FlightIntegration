# LINE 帳號綁定功能
# 把 LINE user_id 存到 User.User_LineId 欄位

import pymssql
from typing import Optional

# DB 連線設定（跟 ticket_service 一樣）
# FIXME: 之後應該改成從環境變數讀取
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}


def get_user_id_by_line(line_user_id: str) -> Optional[str]:
    """用 LINE user_id 查綁定的網站帳號，沒綁定就回 None"""
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()
        cursor.execute("SELECT User_Id FROM [User] WHERE User_LineId = %s", (line_user_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except pymssql.Error:
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def bind_line_user(user_id: str, line_user_id: str) -> dict:
    """
    綁定 LINE 帳號到網站帳號
    一個 LINE 只能綁一個網站帳號，要先檢查有沒有重複
    """
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()

        # 先看這個 LINE 有沒有被別人綁走
        cursor.execute(
            "SELECT User_Id FROM [User] WHERE User_LineId = %s AND User_Id != %s",
            (line_user_id, user_id)
        )
        if cursor.fetchone():
            return {
                "success": False,
                "error": "此 LINE 帳號已綁定其他使用者",
                "message": "此 LINE 帳號已綁定其他使用者，請先解除綁定"
            }

        cursor.execute(
            "UPDATE [User] SET User_LineId = %s, Modify_At = GETDATE() WHERE User_Id = %s",
            (line_user_id, user_id)
        )

        if cursor.rowcount == 0:
            return {"success": False, "error": "使用者不存在", "message": "找不到該使用者"}

        conn.commit()
        return {"success": True, "message": "綁定成功"}

    except pymssql.Error as e:
        if conn:
            conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def unbind_by_user(user_id: str) -> dict:
    """用網站帳號解除綁定"""
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
    except pymssql.Error as e:
        if conn:
            conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def unbind_by_line(line_user_id: str) -> dict:
    """用 LINE ID 解除綁定"""
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
    except pymssql.Error as e:
        if conn:
            conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

