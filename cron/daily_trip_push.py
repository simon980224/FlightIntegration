"""
每日行程推播 Cron Job
用途：每天早上推播當日行程給用戶
執行時間：每天早上 8:00
"""

import json
import os
import sys
from datetime import datetime, timedelta
from linebot import LineBotApi
from linebot.models import FlexSendMessage

# 確保專案根目錄在 Python 路徑中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.linebot.trip_planner import get_trip_plan, build_daily_trip_flex
from api.linebot.tips import get_multi_day_weather
from service.linebot_service import load_config


def get_today_trip_plans():
    """取得今天需要推播的行程"""
    trip_plans_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "trip_plans.json"
    )
    
    if not os.path.exists(trip_plans_file):
        return []
    
    with open(trip_plans_file, "r", encoding="utf-8") as f:
        all_plans = json.load(f)
    
    today = datetime.now().date()
    today_plans = []
    
    for trip_plan_id, trip_plan in all_plans.items():
        # 檢查每一天的行程
        for day_plan in trip_plan.get("daily_plans", []):
            plan_date = datetime.fromisoformat(day_plan["date"]).date()
            if plan_date == today:
                today_plans.append({
                    "trip_plan_id": trip_plan_id,
                    "line_user_id": trip_plan["line_user_id"],
                    "day_plan": day_plan,
                    "destination": trip_plan["destination"]
                })
    
    return today_plans


def push_daily_trip(line_api: LineBotApi, plan_info: dict):
    """推播當日行程給用戶"""
    try:
        user_id = plan_info["line_user_id"]
        day_plan = plan_info["day_plan"]
        destination = plan_info["destination"]
        
        # 取得當日天氣
        weather_data = get_multi_day_weather(destination, days=1)
        weather_today = None
        if weather_data and weather_data.get("time"):
            weather_today = {
                "max_temp": weather_data["temperature_2m_max"][0],
                "min_temp": weather_data["temperature_2m_min"][0],
                "rain_prob": weather_data["precipitation_probability_max"][0],
                "emoji": "🌤️"
            }
        
        # 建立 Flex Message
        bubble = build_daily_trip_flex(day_plan, weather_today)
        flex_message = FlexSendMessage(
            alt_text=f"今日行程：{day_plan['theme']}",
            contents=bubble
        )
        
        # 推播
        line_api.push_message(user_id, flex_message)
        
        return {
            "success": True,
            "user_id": user_id,
            "day": day_plan["day"],
            "theme": day_plan["theme"]
        }
    
    except Exception as e:
        return {
            "success": False,
            "user_id": plan_info.get("line_user_id", "unknown"),
            "error": str(e)
        }


def main():
    """主函數"""
    print(f"\n{'='*70}")
    print(f"每日行程推播 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # 載入配置
    config = load_config()
    line_api = LineBotApi(config['line_bot']['channel_access_token'])
    
    # 取得今天的行程
    today_plans = get_today_trip_plans()
    print(f"找到 {len(today_plans)} 個今日行程需要推播\n")
    
    if not today_plans:
        print("沒有需要推播的行程")
        return
    
    # 推播行程
    results = []
    for plan_info in today_plans:
        print(f"推播給用戶 {plan_info['line_user_id']} - 第 {plan_info['day_plan']['day']} 天：{plan_info['day_plan']['theme']}")
        result = push_daily_trip(line_api, plan_info)
        results.append(result)
        
        if result["success"]:
            print(f"  ✅ 推播成功")
        else:
            print(f"  ❌ 推播失敗：{result['error']}")
    
    # 統計結果
    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count
    
    print(f"\n{'='*70}")
    print(f"推播完成：成功 {success_count} 個，失敗 {fail_count} 個")
    print(f"{'='*70}\n")
    
    # 記錄日誌
    log_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "logs",
        "CronLog",
        f"{datetime.now().strftime('%Y%m%d')}_trip_push.log"
    )
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"執行時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"推播數量：{len(results)}\n")
        f.write(f"成功：{success_count}，失敗：{fail_count}\n")
        for result in results:
            status = "✅" if result["success"] else "❌"
            f.write(f"{status} {result}\n")


if __name__ == "__main__":
    main()

