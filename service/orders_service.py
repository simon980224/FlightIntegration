# service/orders_service.py
# 依使用者查詢真實訂票（Ticket）資料，JOIN Flight/Airport 以產出前端需要欄位

from typing import List, Dict
import pymssql
from datetime import datetime

# 與現有服務使用同一組連線設定（可後續抽共用）
conn_args = {
    "server": "140.131.114.241",
    "user": "adminfid",
    "password": "Flight_admin123@",
    "database": "114-FlightIntegration_DB",
}

def _fmt_date(dt: datetime) -> str:
    try:
        return dt.strftime('%Y-%m-%d') if isinstance(dt, datetime) else str(dt)[:10]
    except Exception:
        return str(dt)

def _fmt_time(dt: datetime) -> str:
    try:
        return dt.strftime('%H:%M') if isinstance(dt, datetime) else str(dt)[11:16]
    except Exception:
        return str(dt)


def get_tickets_by_user(user_id: str) -> List[Dict]:
    """
    回傳清單：[{ no, from, to, date, dep, arr, cabin, price }]
    若無資料回空 list。
    """
    rows = []
    conn = None
    cursor = None
    try:
        conn = pymssql.connect(**conn_args)
        cursor = conn.cursor(as_dict=True)
        sql = """
SELECT 
    T.Ticket_Id,
    F.No               AS Flight_No,
    DAP.Airport_Name_ZH AS From_Airport_ZH,
    AAP.Airport_Name_ZH AS To_Airport_ZH,
    F.D_Time,
    F.A_Time,
    T.Cabin_Class,
    T.Price
FROM dbo.Ticket AS T
JOIN dbo.Flight AS F       ON T.Flight_Id = F.Flight_Id
LEFT JOIN dbo.Airport AS DAP ON F.D_Airport_Id = DAP.Airport_Id
LEFT JOIN dbo.Airport AS AAP ON F.A_Airport_Id = AAP.Airport_Id
WHERE T.User_Id = %s
ORDER BY F.D_Time DESC
        """
        cursor.execute(sql, (user_id,))
        for r in cursor.fetchall():
            rows.append({
                'no': r.get('Flight_No') or r.get('No'),
                'from': r.get('From_Airport_ZH') or '',
                'to': r.get('To_Airport_ZH') or '',
                'date': _fmt_date(r.get('D_Time')),
                'dep': _fmt_time(r.get('D_Time')),
                'arr': _fmt_time(r.get('A_Time')),
                'cabin': r.get('Cabin_Class') or '經濟艙',
                'price': str(r.get('Price') or 0),
            })
        return rows
    except Exception:
        return []
    finally:
        try:
            if cursor: cursor.close()
        finally:
            if conn: conn.close()

