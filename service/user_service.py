import pymssql
import hashlib

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