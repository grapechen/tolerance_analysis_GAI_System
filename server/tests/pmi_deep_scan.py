import sys
try:
    import OCC.Core.XCAFDoc as XCAFDoc
except ImportError:
    print("❌ 無法載入 XCAFDoc，請確認 Conda 環境。")
    sys.exit(1)

def full_module_scan():
    print("=====================================================")
    print("🛡️  OCC.Core.XCAFDoc 深度模組掃描")
    print("=====================================================")
    
    all_items = dir(XCAFDoc)
    # 過濾出與公差、尺寸、數據相關的關鍵字
    keywords = ["Dim", "Tol", "GDT", "Datum", "Object", "Representation"]
    pmi_related = [i for i in all_items if any(k in i for k in keywords)]
    
    print(f"✅ 找到 {len(pmi_related)} 個公差/數據相關類別與方法：")
    for item in sorted(pmi_related):
        # 標註哪些是類別，哪些是工具函式
        attr = getattr(XCAFDoc, item)
        typ = " [Class]" if isinstance(attr, type) else ""
        print(f" - {item}{typ}")

if __name__ == "__main__":
    full_module_scan()
