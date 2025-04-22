from flask import Flask, render_template, request
from service import search_service
import pyodbc

app = Flask(__name__)

# 首頁顯示所有資料
@app.route('/')
def index():
    flight_data = search_service.get_flight_data()
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    return render_template('index.html', title='首頁',
                           flight_data=flight_data,
                           airport_data=airport_data,
                           airline_data=airline_data)

# 查詢頁
@app.route('/search', methods=['GET', 'POST'])
def search():
    airport_data = search_service.get_airport_data()
    airline_data = search_service.get_airline_data()
    flights = []

    # 預設空的表單資料
    form_data = {
        "from_airport": "",
        "to_airport": "",
        "departure_date": "",
        "arrival_date": "",
        "airline_ids": [],
        "sort_field": "",
        "sort_order": ""
    }

    if request.method == 'POST':
        from_id = request.form.get('from_airport') or ""
        to_id = request.form.get('to_airport') or ""
        departure_date = request.form.get('departure_date') or ""
        arrival_date = request.form.get('arrival_date') or ""
        airline_ids = request.form.getlist('airline_ids') or []
        sort_field = request.form.get('sort_field') or ""
        sort_order = request.form.get('sort_order') or ""

        # 更新表單資料（供渲染頁面使用）
        form_data = {
            "from_airport": from_id,
            "to_airport": to_id,
            "departure_date": departure_date,
            "arrival_date": arrival_date,
            "airline_ids": airline_ids,
            "sort_field": sort_field,
            "sort_order": sort_order
        }

        # ✅ 新增條件：只有當 from_id 和 to_id 都有值且相等時才阻止
        block_search = from_id and to_id and from_id == to_id

        if not block_search:
            if not any([from_id, to_id, departure_date, arrival_date, airline_ids]):
                print("✅ 無查詢條件，列出所有航班")
                flights = search_service.search_flights()
            else:
                flights = search_service.search_flights(
                    from_id=from_id,
                    to_id=to_id,
                    dep_time=departure_date,
                    arr_time=arrival_date,
                    airline_ids=airline_ids,
                    sort_by=sort_field,
                    sort_order=sort_order
                )
        else:
            print("⚠️ 出發地與目的地不可相同，查詢取消")


    return render_template('search.html',
                           airport_data=airport_data,
                           airline_data=airline_data,
                           flights=flights,
                           form_data=form_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
