import pymssql
import hashlib
import datetime

# 連接字串配置
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

# 驗證用戶登入 密碼用hash加密進行驗證
def AuthenticateUser(user_id, password):
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)

        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

        query = """
SELECT *
FROM [User]
WHERE User_Id = %s AND Password_Hash = %s
        """
        cursor.execute(query, (user_id, password_hash))
        results = cursor.fetchall()
        if results:
            return {"success": True, "data": results}
        else:
            return {"success": False, "message": "使用者名稱或密碼錯誤"}
    except Exception as e:
        return {"success": False, "data": [], "error": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    
# 註冊用戶：寫入 User_Id、User_Name、密碼雜湊與建立時間
def RegisterUser(user_id, user_name, password):
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()

        # 產生密碼雜湊
        password_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

        # 檢查是否重複註冊
        cursor.execute("SELECT COUNT(*) FROM [User] WHERE User_Id = %s", (user_id,))
        if cursor.fetchone()[0] > 0:
            return {"success": False, "message": "使用者已存在"}

        now = datetime.datetime.now()

        # 寫入新使用者（User_Img 可為 NULL，這邊先放空字串或 None）
        cursor.execute("""
            INSERT INTO [User] (User_Id, User_Name, Password_Hash, User_Img, Create_At, Modify_At)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, user_name, password_hash, None, now, now))
        conn.commit()

        return {"success": True, "message": "註冊成功"}

    except Exception as e:
        return {"success": False, "message": f"註冊失敗：{str(e)}"}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()