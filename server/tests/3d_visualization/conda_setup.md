# Conda 環境配置指南 (3D 視覺化與 PMI 讀取)

為了在專案中支持 **OpenCascade (python-occ)** 讀取 STEP AP242 的 PMI 數據，請依照以下步驟配置你的環境。

## 1. 安裝環境
請打開你的 **Anaconda Prompt** 或 **Miniconda Prompt**，執行以下指令：

```powershell
# 建立獨立環境 (推薦 Python 3.11)
conda create -n tol_3d python=3.11 -y

# 啟用環境
conda activate tol_3d

# 安裝核心幾何處理庫 (python-occ)
conda install -c conda-forge pythonocc-core -y

# 安裝資料處理庫
pip install pandas openpyxl
```

## 2. 測試環境
安裝完成後，你可以嘗試執行同目錄下的 `step_pmi_reader.py`：

```powershell
python c:\Tolerance_Project\server\tests\3d_visualization\step_pmi_reader.py
```

## 3. 在 VS Code 中使用
1. 在 VS Code 右下角點擊現有的 Python 解譯器名稱。
2. 在彈出的清單中選擇 `tol_3d` (conda)。

---

## 為什麼要用 Conda？
- **python-occ** 的二進位檔 (DLLs) 非常複雜，普通 `pip` 常因編譯問題失敗。
- Conda 會自動處理 **OCCT (Open CASCADE Technology)** 的底層 C++ 依賴，這對讀取 **XCAF (PMI)** 至關重要。
