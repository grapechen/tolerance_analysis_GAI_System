from flask import Flask, request
import pandas as pd

app = Flask(__name__)

# =========================
# ISO 286 查表
# =========================
def get_iso_tolerance(diameter):
    # 單位: μm
    table = [
        (3,   10, 14),
        (6,   12, 18),
        (10,  15, 22),
        (18,  18, 27),
        (30,  21, 33),
        (50,  25, 39),
        (80,  30, 46),
        (120, 35, 54),
        (180, 40, 63),
        (250, 46, 72),
        (315, 52, 81),
        (400, 57, 89),
        (500, 63, 97)
    ]
    for limit, it7, it8 in table:
        if diameter <= limit:
            return it7, it8
    return 63, 97


# =========================
# Web UI
# =========================
@app.route("/")
def index():
    diameter = request.args.get("d", "")
    safety = request.args.get("s", "3")

    html = """
    <html>
    <head>
        <meta charset="utf-8">
        <title>機台精度篩選系統</title>
    </head>
    <body>
        <h2>🛠️ 機台精度篩選（ISO 286）</h2>

        <form method="get">
            名義直徑 (mm):
            <input name="d" value="{d}" required>

            Safety factor:
            <input name="s" value="{s}" required>

            <button type="submit">計算</button>
        </form>
        <hr>
    """

    if diameter:
        d = float(diameter)
        s = float(safety)

        it7_um, it8_um = get_iso_tolerance(d)
        tol_g7 = it7_um / 1000.0
        tol_H8 = it8_um / 1000.0

        target_repeat = tol_g7 / s

        html += f"""
        <h3>📐 公差分析</h3>
        <ul>
            <li>H8 公差：{tol_H8:.3f} mm</li>
            <li>g7 公差：{tol_g7:.3f} mm</li>
            <li>建議機台重現精度 ≤ <b>{target_repeat:.4f} mm</b></li>
        </ul>
        """

        try:
            df = pd.read_csv(r"c:\\Users\\tony\\Desktop\\碩一\\py\\PY1\\備份.csv")
            ok = df[df["重現精度(mm)"] <= target_repeat]

            if not ok.empty:
                html += """
                <h3>✅ 符合機台</h3>
                <table border="1" cellpadding="5">
                    <tr>
                        <th>型號</th>
                        <th>公司</th>
                        <th>重現精度 (mm)</th>
                        <th>定位精度 (mm)</th>
                    </tr>
                """
                for _, r in ok.iterrows():
                    html += f"""
                    <tr>
                        <td>{r['型號']}</td>
                        <td>{r['公司']}</td>
                        <td>{r['重現精度(mm)']}</td>
                        <td>{r['定位精度(mm)']}</td>
                    </tr>
                    """
                html += "</table>"
            else:
                html += "<p>❌ 沒有符合精度的機台</p>"

        except Exception as e:
            html += f"<p>⚠ 讀取資料錯誤：{e}</p>"

    html += "</body></html>"
    return html.format(d=diameter, s=safety)


# =========================
# 啟動
# =========================
if __name__ == "__main__":
    app.run(debug=True)
