import pandas as pd

# ==========================================
# 設定顯示參數
# ==========================================
pd.set_option('display.max_rows', None)      # 顯示所有列
pd.set_option('display.max_columns', None)   # 顯示所有欄
pd.set_option('display.unicode.east_asian_width', True) # 讓中文寬度判斷準確一點

# ==========================================
# 讀取檔案
# ==========================================
# 請確認您的路徑是否正確
df = pd.read_csv(r'c:\Users\tony\Desktop\碩一\py\PY1\活頁簿1.csv')

# ==========================================
# 分割資料
# ==========================================
df_repeatability = df[['重現精度(mm)']]
df_others = df.drop(columns=['重現精度(mm)'])

# ==========================================
# 顯示結果 (關鍵修改在這邊)
# ==========================================
# col_space=25 代表每個欄位至少保留 25 個字元的寬度
# justify='left' 讓文字靠左對齊，通常比較好閱讀

print(f"處理完成！共讀取 {len(df)} 筆資料。\n")

print("=== 第一格：重現精度 (全部資料) ===")
print(df_repeatability.to_string(col_space=10, justify='left'))

print("\n" + "="*50 + "\n")

print("=== 第二格：其餘資料 (全部資料) ===")
print(df_others.to_string(col_space=15, justify='left'))

# ==========================================
# 儲存檔案
# ==========================================
df_repeatability.to_csv('repeatability_all.csv', index=False, encoding='utf-8-sig')
df_others.to_csv('others_all.csv', index=False, encoding='utf-8-sig')