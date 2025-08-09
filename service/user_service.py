import pymssql
import hashlib
import datetime
import os
import uuid
from werkzeug.utils import secure_filename

# 連接字串配置
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

# 設定上傳資料夾路徑
UPLOAD_FOLDER = os.path.join('static', 'user_photos')

# 產生亂數檔名
def generate_random_filename(extension):
    return f"{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}{extension}"

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
def RegisterUser(user_id, user_name, password, user_email):
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
INSERT INTO [User] (User_Id, User_Name, Password_Hash, User_Email, User_Img, User_Grade, Create_At, Modify_At)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, user_name, password_hash, user_email, None, '001' , now, now))
        conn.commit()

        return {"success": True, "message": "註冊成功"}

    except Exception as e:
        return {"success": False, "message": f"註冊失敗：{str(e)}"}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def GetUserInfo(user_id):
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)

        cursor.execute("SELECT * FROM [User] WHERE User_Id = %s", (user_id,))
        user_info = cursor.fetchone()

        if user_info:
            return {"success": True, "data": user_info}
        else:
            return {"success": False, "message": "查無此使用者"}

    except Exception as e:
        return {"success": False, "message": f"查詢失敗：{str(e)}"}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def UpdateUserInfo(
    user_id,
    user_name=None,
    old_password=None,
    new_password=None,
    user_img=None,  # 這是 request.files['user_img'] 傳進來的 FileStorage
):
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)

        # 驗證舊密碼（若要修改密碼時才驗證）
        if new_password:
            if not old_password:
                return {"success": False, "message": "請提供舊密碼以修改新密碼"}
            
            old_password_hash = hashlib.sha256(old_password.encode('utf-8')).hexdigest()

            cursor.execute("SELECT * FROM [User] WHERE User_Id = %s AND Password_Hash = %s",
                           (user_id, old_password_hash))
            if not cursor.fetchone():
                return {"success": False, "message": "舊密碼錯誤，無法修改密碼"}
            if new_password == old_password:
                return {"success": False, "message": "新密碼不能與舊密碼相同"}

        # 準備更新欄位
        fields = []
        params = []
        modify_at = datetime.datetime.now()

        if user_name is not None:
            fields.append("User_Name = %s")
            params.append(user_name)

        if new_password:
            new_password_hash = hashlib.sha256(new_password.encode('utf-8')).hexdigest()
            fields.append("Password_Hash = %s")
            params.append(new_password_hash)

        if user_img and user_img.filename != "":
            ext = os.path.splitext(secure_filename(user_img.filename))[-1]
            filename = generate_random_filename(ext)

            # 確保資料夾存在
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

            save_path = os.path.join(UPLOAD_FOLDER, filename)
            user_img.save(save_path)

            fields.append("User_Img = %s")
            params.append(filename)


        fields.append("Modify_At = %s")
        params.append(modify_at)

        if not fields:
            return {"success": False, "message": "沒有提供任何要更新的欄位"}

        # 組成 SQL 更新語句
        query = f"""
UPDATE [User]
SET {', '.join(fields)}
WHERE User_Id = %s
        """
        params.append(user_id)

        cursor.execute(query, tuple(params))
        conn.commit()

        if cursor.rowcount == 0:
            return {"success": False, "message": "查無此使用者，更新失敗"}

        return {"success": True, "message": "使用者資料更新成功"}

    except Exception as e:
        return {"success": False, "message": f"更新失敗：{str(e)}"}

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()