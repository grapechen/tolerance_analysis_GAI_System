# 故障排除指南

## 常見安裝問題

### 1. Python 找不到或版本過舊

**症狀：**
```
'python' 不是內部或外部命令
```

**解決方法：**
- 從 [python.org](https://www.python.org/downloads/) 下載 Python 3.8+
- 安裝時勾選 "Add Python to PATH"
- 重新開啟終端機

### 2. 虛擬環境建立失敗

**症狀：**
```
Error: Unable to create virtual environment
```

**解決方法：**
```bash
# Windows
python -m pip install --upgrade pip
python -m venv .venv --clear

# Linux/Mac
python3 -m pip install --upgrade pip
python3 -m venv .venv --clear
```

### 3. 套件安裝失敗

**症狀：**
```
ERROR: Could not install packages
```

**解決方法：**
1. 檢查網路連線
2. 更新 pip：
   ```bash
   .venv\Scripts\python.exe -m pip install --upgrade pip
   ```
3. 逐個安裝套件找出問題：
   ```bash
   .venv\Scripts\python.exe -m pip install flask
   .venv\Scripts\python.exe -m pip install sqlalchemy
   ```

### 4. MySQL 連線失敗

**症狀：**
```
❌ 資料庫連線失敗: Can't connect to MySQL server
```

**解決方法：**
1. 確認 MySQL 服務已啟動
2. 檢查 `server/tables.py` 中的連線字串：
   ```python
   engine = create_engine(
       "mysql+pymysql://root:密碼@127.0.0.1:3307/tol?charset=utf8mb4"
   )
   ```
3. 確認：
   - 使用者名稱（預設 `root`）
   - 密碼
   - 埠號（預設 `3306` 或 `3307`）
   - 資料庫名稱（`tol`）

### 5. Ollama 不可用

**症狀：**
```
⚠️ Ollama 不可用
```

**解決方法：**
1. 下載並安裝 Ollama：https://ollama.com/download
2. 啟動 Ollama 應用程式
3. 下載模型：
   ```bash
   ollama pull gemma3:4b
   ```
4. 驗證：
   ```bash
   ollama list
   ```

## 執行時問題

### 1. Port 已被佔用

**症狀：**
```
OSError: [Errno 48] Address already in use
```

**解決方法：**

**Windows:**
```cmd
netstat -ano | findstr :7010
taskkill /PID <PID> /F
```

**Linux/Mac:**
```bash
lsof -ti:7010 | xargs kill -9
```

### 2. 模組找不到

**症狀：**
```
ModuleNotFoundError: No module named 'flask'
```

**解決方法：**
確認使用虛擬環境中的 Python：
```bash
# Windows
.venv\Scripts\python.exe server/app.py

# Linux/Mac
source .venv/bin/activate
python server/app.py
```

### 3. 資料表不存在

**症狀：**
```
sqlalchemy.exc.ProgrammingError: Table 'tol.iso286_tolerance' doesn't exist
```

**解決方法：**
執行資料庫初始化：
```bash
.venv\Scripts\python.exe server/tables.py
.venv\Scripts\python.exe server/import_all_data.py
```

## 效能問題

### 1. AI 回應太慢

**可能原因：**
- 使用的模型太大
- 本地硬體資源不足

**解決方法：**
1. 切換到較小的模型：
   - `gemma3:4b` (推薦，4GB)
   - `llama3.1:8b` (8GB)
2. 使用雲端模型（需登入 Ollama）：
   - `gpt-oss:20b-cloud`
   - `gemma3:12b`

### 2. 資料庫查詢慢

**解決方法：**
1. 確認已建立索引（`tables.py` 中已定義）
2. 檢查 MySQL 效能設定
3. 考慮使用快取（Redis）

## 平台特定問題

### Windows

**問題：Gunicorn 安裝失敗**
- **正常現象**：Gunicorn 不支援 Windows
- **解決方法**：使用 `run_basic.bat` 和 `run_ai.bat`（開發用）

**問題：權限錯誤**
- 以系統管理員身分執行終端機

### Linux/Mac

**問題：Permission denied**
```bash
chmod +x setup.sh run_basic.sh run_ai.sh run_production.sh
```

**問題：MySQL socket 錯誤**
- 檢查 MySQL socket 路徑
- 使用 TCP 連線而非 socket

## 驗證環境

執行驗證腳本檢查所有設定：

```bash
# Windows
.venv\Scripts\python.exe validate_setup.py

# Linux/Mac
python validate_setup.py
```

## 取得協助

如果問題仍未解決：

1. 檢查日誌檔案：
   - `logs/app.log` - 應用程式日誌
   - `logs/ai.log` - AI 助手日誌

2. 執行診斷：
   ```bash
   .venv\Scripts\python.exe -m pip check
   .venv\Scripts\python.exe validate_setup.py
   ```

3. 收集資訊：
   - Python 版本：`python --version`
   - 作業系統版本
   - 錯誤訊息完整內容
   - 相關日誌檔案內容
