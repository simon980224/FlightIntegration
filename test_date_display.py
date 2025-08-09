#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試日期顯示功能
"""

from service.linebot_service import process_line_message

def test_date_display():
    test_messages = [
        '明天桃園到東京',
        '8/7桃園到東京',
        '昨天桃園到東京'
    ]

    for msg in test_messages:
        print(f'原始訊息: {msg}')

        try:
            result = process_line_message(msg, 'test_user')
            first_line = result.split('\n')[0]
            print(f'查詢結果標題: {first_line}')
        except Exception as e:
            print(f'錯誤: {e}')

        print('-' * 50)

if __name__ == "__main__":
    test_date_display()
