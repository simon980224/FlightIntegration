from datetime import datetime
from curl_cffi import requests as cfre
import pyodbc

def connect_db():
    return pyodbc.connect(
        "Driver={ODBC Driver 17 for SQL Server};"
        "Server=140.131.114.241;"
        "Database=114-FlightIntegration_DB;" 
        "UID=adminfid;"
        "PWD=Flight_admin123@;"
    )

def query_today_departures():
    today_str = datetime.now().strftime("%Y/%m/%d")
    payload = {
        "ODate": today_str,
        "OTimeOpen": "00:00",
        "OTimeClose": "23:59",
        "BNO": None,
        "AState": "D",
        "language": "ch",
        "keyword": ""
    }

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": "https://www.taoyuan-airport.com",    
        "referer": "https://www.taoyuan-airport.com/flight_depart",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )
    }

    url = "https://www.taoyuan-airport.com/api/api/flight/a_flight"

    try:
        resp = cfre.post(
            url,
            headers=headers,
            json=payload,
            impersonate="chrome120",
            timeout=30
        )

        flights = resp.json()
        print("✅ 回傳筆數：", len(flights))
        if not flights:
            print("⚠ 沒有資料")
            return

        airlines = set()
        airports = set()
        flight_rows = []

        fmt = "%Y/%m/%d %H:%M:%S"

        for flight in flights:
            Flight_Id = flight.get("id") or ''
            Airline_Id = flight.get("ACode") or ''
            Airline_Name_ZH = flight.get("AName") or ''
            iflyprint1Status = flight.get("CurrentStatus") or '0'
            Status = 1 if iflyprint1Status == '已飛' else iflyprint1Status

            # ✅ 修正後：出發是 TPE，到達是 CityCode（目的地）
            D_Airport_Id = 'TPE'
            A_Airport_Id = flight.get("CityCode") or 'UNKNOWN'

            # 出發／到達機場名稱
            D_Airport_Name = "Taoyuan"
            D_Airport_Name_ZH = "桃園國際機場"
            A_Airport_Name = flight.get("CityEname") or ''
            A_Airport_Name_ZH = flight.get("CityName") or ''

            # 時間處理
            fmt = "%Y/%m/%d %H:%M:%S"
            try:
                D_Time = datetime.strptime(flight["ODate"] + " " + flight["OTime"], fmt)
            except:
                D_Time = datetime.now()
            try:
                A_Time = datetime.strptime(flight["RDate"] + " " + flight["RTime"], fmt)
            except:
                A_Time = None

            # 資料彙整
            airlines.add((Airline_Id, Airline_Name_ZH))
            airports.add((D_Airport_Id, D_Airport_Name, D_Airport_Name_ZH))
            airports.add((A_Airport_Id, A_Airport_Name, A_Airport_Name_ZH))

            flight_rows.append((
                Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id,
                D_Time, A_Time, Status
            ))

        

        # 寫入資料庫
        conn = connect_db()
        cursor = conn.cursor()

        # Airline insert if not exists

        for aid, aname_zh in airlines:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM Airline WHERE Airline_Id = ?)
                BEGIN
                    INSERT INTO Airline (Airline_Id, Airline_Name, Airline_Name_ZH)
                    VALUES (?, '', ?)
                END
                ELSE
                BEGIN
                    UPDATE Airline
                    SET 
                        Airline_Name_ZH = CASE 
                            WHEN Airline_Name_ZH IS NULL OR Airline_Name_ZH = '' 
                            THEN ? ELSE Airline_Name_ZH 
                        END
                    WHERE Airline_Id = ?
                END
            """, aid, aid, aname_zh, aname_zh, aid)




        # Airport insert if not exists
        for apid, ename, zhname in airports:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM Airport WHERE Airport_Id = ?)
                INSERT INTO Airport (Airport_Id, Airport_Name, Airport_Name_ZH)
                VALUES (?, ?, NULL)
            """, apid, apid, ename)

        # Flight insert or update
        insert_rows = []
        update_rows = []

        for row in flight_rows:
            cursor.execute("SELECT 1 FROM Flight WHERE Flight_Id = ?", row[0])
            if cursor.fetchone():
                update_rows.append(row)
            else:
                insert_rows.append(row)
        if insert_rows:
            cursor.executemany("""
                INSERT INTO Flight (
                    Flight_Id, Airline_Id, D_Airport_Id, A_Airport_Id,
                    D_Time, A_Time, Status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, insert_rows)
        
        conn.commit()
        cursor.close()
        conn.close()

        print(f"\n📊 資料庫更新結果：新增 {len(insert_rows)} 筆，更新 {len(update_rows)} 筆")

    except Exception as e:
        print("❌ 查詢或寫入失敗：", e)

if __name__ == "__main__":
    query_today_departures()
