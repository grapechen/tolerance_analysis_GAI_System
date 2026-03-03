# 🚀 ISO 286 公差查詢系統 - 部署檢查清單

本檢查清單基於生產環境最佳實踐，確保系統安全、穩定、可維護。

## 🛡️ 第一道防線：安全性與資安

### 1. 環境變數管理
- [ ] ✅ `.env` 文件已加入 `.gitignore`
- [ ] ✅ `.env.example` 已創建並包含所有必要變數
- [ ] 🔒 生產環境的 `.env` 已設置並包含真實密碼
- [ ] 🔒 資料庫密碼使用強密碼（至少 16 字元）
- [ ] 🔒 確認沒有將 `.env` 提交到版本控制

### 2. API 路由保護
- [ ] ✅ 已實作速率限制（Rate Limiting）
  - API 查詢：60 次/分鐘
  - AI 查詢：10 次/分鐘
- [ ] ✅ 錯誤訊息已清理，不洩露敏感資訊
- [ ] ⚠️ 考慮添加 API Key 認證（如需公開部署）

### 3. 資料庫安全
- [ ] 🔒 MySQL 不使用 root 帳號（建議創建專用帳號）
- [ ] 🔒 資料庫只允許本地連線（127.0.0.1）
- [ ] 🔒 定期備份資料庫
- [ ] 📝 資料庫連線使用連線池（已在 SQLAlchemy 中實作）

### 4. CORS 設定
- [ ] ⚠️ 當前設定：允許所有來源 (`origins: '*'`)
- [ ] 🔧 生產環境建議：限制為特定域名
  ```python
  CORS(app, resources={r'/*': {'origins': ['https://yourdomain.com']}})
  ```

### 5. 輸入驗證
- [ ] ✅ 所有 API 端點都有參數驗證
- [ ] ✅ 使用 try-except 處理異常
- [ ] ✅ 數值範圍檢查（尺寸、公差等級）

## 💰 第二道防線：成本與維運

### 6. 日誌與監控
- [ ] ✅ 已實作統一日誌系統（logger.py）
- [ ] ✅ 日誌文件已加入 `.gitignore`
- [ ] 📝 日誌級別設定：
  - 開發環境：DEBUG
  - 生產環境：INFO
- [ ] 🔧 建議：設定日誌輪轉（避免日誌文件過大）

### 7. 效能優化
- [ ] 📝 資料庫查詢已優化（使用索引）
- [ ] 📝 考慮添加快取（Redis）以減少資料庫查詢
- [ ] 📝 AI 查詢使用速率限制防止濫用

### 8. 資源限制
- [ ] 🔧 設定 Flask 的 worker 數量
- [ ] 🔧 設定最大請求大小限制
- [ ] 🔧 設定超時時間（避免長時間佔用資源）

## 🧠 第三道防線：體驗與維護

### 9. 錯誤處理
- [ ] ✅ 自定義錯誤訊息（不洩露技術細節）
- [ ] ✅ 所有 API 返回統一格式：`{"ok": bool, "msg": str, ...}`
- [ ] 📝 前端有友善的錯誤提示

### 10. 清理除錯資訊
- [ ] ✅ 移除或替換 `print()` 為 `logger`
- [ ] ⚠️ 生產環境關閉 Flask debug 模式
  ```python
  app.run(debug=False)  # 生產環境必須設為 False
  ```
- [ ] 📝 移除測試用的 console.log（前端）

### 11. 文件完整性
- [ ] ✅ README.md 包含完整的安裝和使用說明
- [ ] ✅ API 文件清楚（或考慮使用 Swagger）
- [ ] ✅ 離線版本有獨立說明（client/README.md）
- [ ] ✅ 環境變數有範例文件（.env.example）

## 🤖 AI 應用特定檢查

### 12. Ollama 配置
- [ ] 📝 確認 Ollama 服務正常運行
- [ ] 📝 已下載必要的模型
- [ ] 🔧 設定模型載入超時時間
- [ ] 💰 雲端模型已設定使用限制（避免超額）

### 13. Prompt 安全
- [ ] ✅ System Prompt 在後端，不暴露給前端
- [ ] 📝 考慮添加 Prompt Injection 防護
- [ ] 📝 用戶輸入有長度限制

### 14. 成本控制
- [ ] 💰 AI 查詢有速率限制（10 次/分鐘）
- [ ] 💰 考慮添加用戶配額系統
- [ ] 💰 監控 API 使用量

## 📋 部署前最終檢查

### 環境準備
- [ ] Python 3.8+ 已安裝
- [ ] MySQL/MariaDB 已安裝並運行
- [ ] Ollama 已安裝（如使用 AI 功能）
- [ ] 虛擬環境已創建（.venv）

### 資料庫初始化
- [ ] 執行 `python server/tables.py` 創建資料表
- [ ] 執行 `python server/import_all_data.py` 匯入資料
- [ ] 驗證資料完整性（約 5000 筆）

### 服務測試
- [ ] 基本查詢系統可正常啟動（port 7010）
- [ ] AI 助手可正常啟動（port 7011）
- [ ] 所有 API 端點測試通過
- [ ] 離線版本可正常開啟

### 安全檢查
- [ ] 防火牆規則已設定
- [ ] 只開放必要的端口
- [ ] SSL/TLS 證書已配置（如需外網訪問）
- [ ] 定期更新依賴套件

## 🔧 生產環境建議配置

### 使用 Gunicorn（推薦）
```bash
# 安裝
pip install gunicorn

# 啟動基本查詢系統
gunicorn -w 4 -b 0.0.0.0:7010 server.app:app

# 啟動 AI 助手
gunicorn -w 2 -b 0.0.0.0:7011 --timeout 120 server.ai_app:app
```

### 使用 Nginx 反向代理
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:7010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ai/ {
        proxy_pass http://127.0.0.1:7011/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

### 使用 Systemd 服務（Linux）
創建 `/etc/systemd/system/iso286-basic.service`：
```ini
[Unit]
Description=ISO 286 Basic Query Service
After=network.target mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/Tolerance_Project
Environment="PATH=/path/to/Tolerance_Project/.venv/bin"
ExecStart=/path/to/Tolerance_Project/.venv/bin/gunicorn -w 4 -b 127.0.0.1:7010 server.app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📊 監控指標

建議監控以下指標：
- [ ] API 請求數量和回應時間
- [ ] 錯誤率（4xx, 5xx）
- [ ] 資料庫連線數
- [ ] 記憶體使用量
- [ ] CPU 使用率
- [ ] 磁碟空間（日誌文件）

## 🆘 故障排除

### 常見問題
1. **資料庫連線失敗**
   - 檢查 MySQL 服務是否運行
   - 檢查 .env 中的連線資訊
   - 檢查防火牆設定

2. **Ollama 連線失敗**
   - 確認 Ollama 服務運行中
   - 檢查模型是否已下載
   - 查看 Ollama 日誌

3. **速率限制觸發**
   - 正常現象，保護系統
   - 可調整 middleware.py 中的限制參數

## ✅ 部署完成確認

- [ ] 所有服務正常運行
- [ ] 可以從瀏覽器訪問
- [ ] API 測試通過
- [ ] 日誌正常記錄
- [ ] 錯誤處理正常
- [ ] 效能符合預期

---

**最後更新**: 2024-12-11  
**版本**: 1.0  
**維護者**: [Your Name]
