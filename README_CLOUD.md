# ISO 286 公差分析系統 - Ollama Cloud API 版本

> ⚠️ **此文件已過時** - 現在推薦使用統一的 AI 助手（`ai_app.py`），可在介面中直接切換本地和雲端模型。
> 
> 請參考：[docs/cloud_models_guide.md](docs/cloud_models_guide.md)

---

## 舊版說明（僅供參考）

這是使用 **Ollama Cloud API** 的純雲端版本，無需在本地安裝 Ollama 或下載模型。

**注意**：此版本已被整合到主 AI 助手中，不再需要單獨的雲端版本。

## 🌟 優勢

- ✅ **無需本地安裝** - 不用安裝 Ollama 或下載大型模型
- ✅ **更快的推理速度** - 使用資料中心級 GPU
- ✅ **運行更大的模型** - 可使用本地跑不動的大模型
- ✅ **省電省資源** - 不佔用本地電腦資源
- ✅ **隱私保護** - Ollama 不會保留你的資料

## 📋 前置需求

### 1. Ollama Cloud API Key

訪問 [https://ollama.com/cloud](https://ollama.com/cloud) 註冊並取得 API Key

**方案選擇：**
- **Free（免費）** - $0/月，適合測試和輕度使用
- **Pro** - $20/月，更高使用限制
- **Max** - $100/月，5倍使用限制

### 2. Python 環境

與本地版相同，需要 Python 3.8+ 和 MySQL

## 🚀 快速開始

### 步驟 1：環境設置

如果還沒設置過環境：

```bash
# Windows
setup.bat

# Linux/Mac
./setup.sh
```

### 步驟 2：設定 API Key

**方法 A：環境變數（推薦）**

Windows:
```bash
set OLLAMA_API_KEY=your_api_key_here
```

Linux/Mac:
```bash
export OLLAMA_API_KEY=your_api_key_here
```

**方法 B：建立 .env 檔案**

在專案根目錄建立 `.env` 檔案：
```
OLLAMA_API_KEY=your_api_key_here
```

然後安裝 python-dotenv：
```bash
.venv\Scripts\pip.exe install python-dotenv
```

並在 `server/rag_server_cloud.py` 開頭加入：
```python
from dotenv import load_dotenv
load_dotenv()
```

### 步驟 3：啟動雲端版服務

```bash
run_cloud.bat
```

服務將在 **http://127.0.0.1:7012** 啟動

## 🔄 本地版 vs 雲端版

| 特性 | 本地版 | 雲端版 |
|------|--------|--------|
| **安裝需求** | 需安裝 Ollama + 下載模型 | 只需 API Key |
| **啟動腳本** | `run_ai.bat` | `run_cloud.bat` |
| **服務埠口** | 7011 | 7012 |
| **推理速度** | 取決於本地硬體 | 資料中心級 GPU（更快） |
| **資源佔用** | 佔用本地 CPU/GPU/記憶體 | 不佔用本地資源 |
| **費用** | 免費 | Free 方案免費，有使用限制 |
| **隱私** | 完全本地 | Ollama 不保留資料 |
| **網路需求** | 不需要（推理時） | 需要網路連線 |

## 📁 檔案結構

雲端版新增的檔案：

```
Tolerance_Project/
├── server/
│   ├── ai_app_cloud.py         # Flask 應用（雲端版）
│   └── rag_server_cloud.py     # RAG 服務（雲端版）
├── run_cloud.bat               # 啟動腳本（雲端版）
└── README_CLOUD.md             # 本文件
```

原有的本地版檔案不受影響：
- `server/ai_app.py` - 本地版
- `server/rag_server.py` - 本地版
- `run_ai.bat` - 本地版啟動腳本

## 🎯 使用方式

### 網頁介面

開啟瀏覽器訪問 http://127.0.0.1:7012

介面與本地版相同，但右上角會顯示 "☁️ Cloud" 標誌

### 可用模型

雲端版支援的模型：
- `gemma3:4b` - 預設，快速且準確
- `llama3.1:8b` - 更大的模型
- `qwen3:8b` - 中文優化

可在網頁介面右上角切換模型

## 🔧 故障排除

### Q: 顯示 "未設定 OLLAMA_API_KEY"？

**A:** 確認已設定環境變數：
```bash
# Windows
echo %OLLAMA_API_KEY%

# Linux/Mac
echo $OLLAMA_API_KEY
```

如果沒有輸出，請重新設定 API Key

### Q: API 錯誤 401 Unauthorized？

**A:** API Key 無效或過期，請：
1. 檢查 API Key 是否正確
2. 訪問 https://ollama.com/cloud 確認帳號狀態

### Q: API 錯誤 429 Too Many Requests？

**A:** 超過使用限制，請：
1. 等待一段時間後重試
2. 考慮升級到 Pro 或 Max 方案

### Q: 回應速度慢？

**A:** 可能原因：
1. 網路連線速度
2. 使用的模型較大
3. Ollama Cloud 服務負載

建議切換到較小的模型（如 gemma3:4b）

## 🔐 安全性

- **不要** 將 API Key 提交到 Git
- `.env` 檔案已加入 `.gitignore`
- 建議使用環境變數而非硬編碼

## 📚 相關連結

- [Ollama Cloud 官網](https://ollama.com/cloud)
- [Ollama 文件](https://ollama.com/docs)
- [本地版說明](README.md)

## 💡 建議使用情境

**使用雲端版：**
- 筆記型電腦或低階硬體
- 需要快速回應
- 不想佔用本地資源
- 多人協作環境

**使用本地版：**
- 完全離線環境
- 對隱私有極高要求
- 有強大的本地硬體
- 不想產生 API 費用

## 🎉 開始使用

1. 取得 API Key：https://ollama.com/cloud
2. 設定環境變數：`set OLLAMA_API_KEY=your_key`
3. 啟動服務：`run_cloud.bat`
4. 開啟瀏覽器：http://127.0.0.1:7012

就這麼簡單！
