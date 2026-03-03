from flask import Flask, request

app = Flask(__name__)

# ================== 資料庫 ==================
fits_database = [
    {'type': '留隙配合', 'function': '精確定位', 'shaft': 'H5', 'hole': 'g4', 'ansi': 'RC1', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '定溫', 'shaft': 'H6', 'hole': 'g5', 'ansi': 'RC2', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '低轉速 低軸頸壓力', 'shaft': 'H7', 'hole': 'f6', 'ansi': 'RC3', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '中轉速 中軸頸壓力', 'shaft': 'H8', 'hole': 'f7', 'ansi': 'RC4', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '溫差大 高轉速 高軸頸壓力', 'shaft': 'H8', 'hole': 'e7', 'ansi': 'RC5', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '溫差大 高轉速 高軸頸壓力', 'shaft': 'H9', 'hole': 'e8', 'ansi': 'RC6', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '溫差大 精度不高', 'shaft': 'H9', 'hole': 'd8', 'ansi': 'RC7', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '大公差', 'shaft': 'H10', 'hole': 'c9', 'ansi': 'RC8', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '大公差', 'shaft': 'H11', 'hole': 'c11', 'ansi': 'RC9', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '定位 可裝拆', 'shaft': 'H6', 'hole': 'h5', 'ansi': 'LC1', 'note': '滑動'},
    {'type': '留隙配合', 'function': '定位 可裝拆', 'shaft': 'H7', 'hole': 'h6', 'ansi': 'LC2', 'note': '滑動'},
    {'type': '過渡配合', 'function': '定位 可裝拆', 'shaft': 'H7', 'hole': 'j6', 'ansi': 'LT1', 'note': '輕推'},
    {'type': '過渡配合', 'function': '定位', 'shaft': 'H8', 'hole': 'j7', 'ansi': 'LT2', 'note': '輕推'},
    {'type': '過渡配合', 'function': '準確定位', 'shaft': 'H7', 'hole': 'k6', 'ansi': 'LT3', 'note': '輕打'},
    {'type': '過渡配合', 'function': '準確定位', 'shaft': 'H8', 'hole': 'k7', 'ansi': 'LT4', 'note': '壓入'},
    {'type': '過渡配合', 'function': '準確定位', 'shaft': 'H7', 'hole': 'n6', 'ansi': 'LT5', 'note': '中壓'},
    {'type': '過盈配合', 'function': '剛性 對準', 'shaft': 'H7', 'hole': 'p6', 'ansi': 'LN2', 'note': '重壓'},
    {'type': '過盈配合', 'function': '壓力小 堅固', 'shaft': 'H6', 'hole': 'n5', 'ansi': 'FN1', 'note': '重壓'},
    {'type': '過盈配合', 'function': '壓力小 堅固', 'shaft': 'H6', 'hole': 'p5', 'ansi': 'FN1', 'note': '重壓'},
    {'type': '過盈配合', 'function': '鑄鐵配合使用', 'shaft': 'H7', 'hole': 's6', 'ansi': 'FN2', 'note': '重壓'},
    {'type': '過盈配合', 'function': '壓力大', 'shaft': 'H7', 'hole': 't6', 'ansi': 'FN3', 'note': '重壓'},
    {'type': '過盈配合', 'function': '高應力', 'shaft': 'H7', 'hole': 'u6', 'ansi': 'FN4', 'note': '重壓'},
    {'type': '過盈配合', 'function': '高應力', 'shaft': 'H8', 'hole': 'x7', 'ansi': 'FN5', 'note': '重壓'}
]

# ================== 搜尋邏輯 ==================
def search_fits(keywords):
    results = []
    for item in fits_database:
        row = f"{item['type']} {item['function']} {item['note']}"
        if all(k in row for k in keywords):
            results.append(item)
    return results

# ================== Flask UI ==================
@app.route("/")
def index():
    q = request.args.get("q", "")

    html = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>公差功能配合查詢</title>
    </head>
    <body>
        <h2>🛠️ 公差配合功能查詢系統</h2>

        <form method="get">
            <input name="q" value="{q}" placeholder="例如：定位 過渡 高轉速">
            <button type="submit">查詢</button>
        </form>
        <hr>
    """

    if q:
        keywords = q.split()
        results = search_fits(keywords)

        if results:
            html += """
            <table border="1" cellpadding="5">
                <tr>
                    <th>ANSI</th>
                    <th>孔</th>
                    <th>軸</th>
                    <th>類型</th>
                    <th>功能</th>
                </tr>
            """
            for r in results:
                html += f"""
                <tr>
                    <td>{r['ansi']}</td>
                    <td>{r['hole']}</td>
                    <td>{r['shaft']}</td>
                    <td>{r['type']}</td>
                    <td>{r['function']} ({r['note']})</td>
                </tr>
                """
            html += "</table>"
        else:
            html += "<p>❌ 找不到符合條件的資料</p>"

    html += "</body></html>"
    return html.format(q=q)

# ================== 啟動 ==================
if __name__ == "__main__":
    app.run(debug=True)
