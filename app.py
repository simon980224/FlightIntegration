from flask import Flask, render_template, request, jsonify
from service import search_service
import pyodbc

app = Flask(__name__)

# 頁面 index：同時顯示三組資料
@app.route('/')
def index():
    flight_data = search_service.get_flight_data()
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    return render_template('index.html', title='首頁',
                           flight_data=flight_data,
                           airport_data=airport_data,
                           airline_data=airline_data)

@app.route('/search', methods=['GET', 'POST'])
def search():
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    flights = []

    # ✅ 預設 form_data（避免第一次進入頁面時錯誤）
    form_data = {
        "from_airport": "",
        "to_airport": "",
        "flight_range": "",
        "airline_ids": [],
        "sort_field": "",
        "sort_order": ""
    }

    if request.method == 'POST':
        from_id = request.form.get('from_airport') or ""
        to_id = request.form.get('to_airport') or ""
        flight_range = request.form.get('flight_range') or ""
        airline_ids = request.form.getlist('airline_ids')  # 多選項
        sort_field = request.form.get('sort_field') or ""
        sort_order = request.form.get('sort_order') or ""

        form_data = {
            "from_airport": from_id,
            "to_airport": to_id,
            "flight_range": flight_range,
            "airline_ids": airline_ids,
            "sort_field": sort_field,
            "sort_order": sort_order
        }

        dep_time, arr_time = None, None
        if " 至 " in flight_range:
            dep_time, arr_time = flight_range.split(" 至 ")

        flights = search_service.search_flights(
            from_id=from_id,
            to_id=to_id,
            dep_time=dep_time,
            arr_time=arr_time,
            airline_id=None,  # 如果你已改成 airline_ids 就要支援 list
            sort_by=sort_order  # 這裡依你 search_flights 的設計
        )

    return render_template('search.html',
                           airport_data=airport_data,
                           airline_data=airline_data,
                           flights=flights,
                           form_data=form_data)  # ✅ 傳進 template


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)