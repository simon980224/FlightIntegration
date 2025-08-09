#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 LINE Bot API Log 功能

此檔案用於：
1. 測試 API log 記錄功能是否正常
2. 驗證不同類型的訊息處理
3. 檢查 log 檔案格式和內容
4. 團隊成員學習和展示使用

使用方法：python test_api_log.py
檔案位置：logs/LineBotApiLog/YYYYMMDD.log
"""

from service.linebot_service import process_line_message

def test_api_log():
    """測試 API Log 記錄功能"""
    print("🧪 測試 API Log 功能...")
    
    # 測試案例
    test_cases = [
        {
            "user_id": "U1234567890abcdef",
            "message": "幫助",
            "description": "幫助訊息測試"
        },
        {
            "user_id": "U1234567890abcdef", 
            "message": "查詢航班 台北 東京",
            "description": "航班查詢測試"
        },
        {
            "user_id": "U9876543210fedcba",
            "message": "測試",
            "description": "測試訊息"
        },
        {
            "user_id": "U1111222233334444",
            "message": "隨便說點什麼",
            "description": "預設回應測試"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 測試案例 {i}: {test_case['description']} ---")
        print(f"用戶 ID: {test_case['user_id']}")
        print(f"輸入訊息: {test_case['message']}")
        
        try:
            response = process_line_message(test_case['message'], test_case['user_id'])
            print(f"回應: {response[:100]}...")
            print("✅ 測試成功")
        except Exception as e:
            print(f"❌ 測試失敗: {e}")
    
    print("\n🎯 測試完成！請檢查 logs/ 目錄下的日誌檔案")

if __name__ == "__main__":
    test_api_log()
