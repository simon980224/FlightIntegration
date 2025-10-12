import pymssql
import hashlib
import datetime
import os
import uuid
from werkzeug.utils import secure_filename
import random
import string
import base64
from captcha.image import ImageCaptcha

# 連接字串配置
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB"
}

# 設定上傳資料夾路徑
UPLOAD_FOLDER = os.path.join('static', 'img', 'user_photos')

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
    conn = cursor = None
    try:
        # 基本檢查（最小必要）
        if not user_id or not user_name or not password or not user_email:
            return {"success": False, "message": "缺少必要欄位"}

        # 雜湊密碼
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()

        # 檢查是否重複註冊（User_Id）
        cursor.execute("SELECT COUNT(*) FROM [User] WHERE User_Id = %s", (user_id,))
        if cursor.fetchone()[0] > 0:
            return {"success": False, "message": "使用者已存在"}

        # （可選）若要限制 Email 唯一，解除註解以下兩行
        cursor.execute("SELECT COUNT(*) FROM [User] WHERE User_Email = %s", (user_email,))
        if cursor.fetchone()[0] > 0: return {"success": False, "message": "Email 已被註冊"}

        now = datetime.datetime.now()

        # 僅插入 User 相關欄位（Status/Verify 一律不碰）
        cursor.execute("""
INSERT INTO [User] (
    User_Id, User_Name, Password_Hash, User_Email, User_Img, User_Grade, Status, Create_At, Modify_At
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, user_name, password_hash, user_email, None, '001', '0', now, now))

        conn.commit()

        # 註冊成功後，新增一筆驗證碼資料到 User_Verify_Log
        verify_type = 'register'  # 可依需求調整
        verify_number = str(uuid.uuid4())[:4]  # 產生驗證碼
        verify_value = verify_number  # 這裡直接用驗證碼本身
        status = '0'
        create_at = now
        expired_time = now + datetime.timedelta(minutes=10)  # 驗證碼10分鐘有效

        try:
            cursor.execute("""
INSERT INTO [User_Verify_Log] (User_Id, Verify_Type, Verify_Number, Verify_Value, Status, Create_At, Expired_Time)
VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (user_id, verify_type, verify_number, verify_value, status, create_at, expired_time))
            conn.commit()
        except Exception as e:
            return {"success": True, "message": "註冊成功，但驗證碼寫入失敗：" + str(e)}

        return {"success": True, "message": "註冊成功，驗證碼已產生", "verify_code": verify_number}


    except Exception as e:
        return {"success": False, "message": f"註冊失敗：{e}"}

    finally:
        try:
            cursor and cursor.close()
        finally:
            conn and conn.close()

def VerifyRegisterCode(user_id: str, verification_code: str):

    conn = cursor = None
    try:
        # 基本參數檢查
        if not user_id or not verification_code:
            return {"success": False, "message": "缺少必要欄位"}

        # 連線
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor()

        # 確認使用者是否存在
        cursor.execute("SELECT COUNT(*) FROM [User] WHERE User_Id = %s", (user_id,))
        if cursor.fetchone()[0] == 0:
            return {"success": False, "message": "找不到使用者，請先註冊"}

        # 取最新一筆尚未驗證的紀錄（Verify_Type='register' AND Status=0）
        cursor.execute("""
SELECT TOP 1 Verify_Value, Status, Expired_Time
FROM [User_Verify_Log]
WHERE User_Id = %s AND Verify_Type = 'register' AND Status = 0
ORDER BY Create_At DESC
        """, (user_id,))
        row = cursor.fetchone()

        if not row:
            return {"success": False, "message": "找不到可用的驗證碼，或已驗證過"}

        db_code, status, expired_time = row
        now = datetime.datetime.now()

        # 過期檢查
        if now > expired_time:
            return {"success": False, "message": "驗證碼已過期"}

        # 大小寫敏感比對（不做 lower()/upper()）
        # 僅移除前後空白以避免貼上時夾帶空白
        if str(verification_code).strip() != str(db_code).strip():
            return {"success": False, "message": "驗證碼錯誤（請注意大小寫）"}

        # 驗證成功：更新驗證紀錄與使用者狀態
        cursor.execute("""
UPDATE [User_Verify_Log]
SET Status = 1
WHERE User_Id = %s AND Verify_Type = 'register' AND Status = 0 AND Verify_Value = %s
        """, (user_id, db_code))

        cursor.execute("""
UPDATE [User]
SET Status = '1', Modify_At = %s
WHERE User_Id = %s
        """, (now, user_id))

        conn.commit()
        return {"success": True, "message": "驗證成功"}

    except Exception as e:
        return {"success": False, "message": f"驗證失敗：{e}"}

    finally:
        try:
            cursor and cursor.close()
        finally:
            conn and conn.close()




def UpdateUserInfo(
    user_id,
    user_name=None,
    old_password=None,
    new_password=None,
    user_img=None,  # 這是 request.files['user_img'] 傳進來的 FileStorage
    user_email=None
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

        if user_email is not None:
            fields.append("User_Email = %s")
            params.append(user_email)

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

# 生成圖片驗證碼
def GenerateCaptchaImage():
    """
    生成帶有干擾線的圖片驗證碼
    返回驗證碼文字和圖片的 base64 編碼
    """
    try:
        # 生成 4 位數字驗證碼
        captcha_text = ''.join(random.choices(string.digits, k=4))
        
        # 創建圖片驗證碼生成器
        image = ImageCaptcha(width=160, height=60, fonts=None, font_sizes=(42, 50, 56))
        
        # 生成驗證碼圖片並轉換為 base64
        image_data = image.generate(captcha_text)
        img_base64 = base64.b64encode(image_data.getvalue()).decode('utf-8')
        
        return {
            "success": True,
            "captcha_text": captcha_text,
            "image_base64": f'data:image/png;base64,{img_base64}'
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"驗證碼生成失敗：{str(e)}"
        }

# 驗證 captcha
def VerifyCaptcha(user_input, correct_answer):
    """
    驗證使用者輸入的驗證碼是否正確
    """
    if not user_input:
        return {"success": False, "message": "請輸入驗證碼"}
    
    if not correct_answer:
        return {"success": False, "message": "驗證碼已過期，請重新整理"}
    
    if user_input.strip() != correct_answer:
        return {"success": False, "message": "驗證碼錯誤，請重新輸入"}
    
    return {"success": True}
