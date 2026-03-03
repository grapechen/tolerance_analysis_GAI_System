# RAG 系統使用指南 (MySQL + Ollama)

> ⚠️ **參考文件** - 此文件內容不完整。
> 
> 完整的 RAG 系統說明請參考：[rag_system_guide.md](rag_system_guide.md)
> 
> 使用方式請參考主 README.md

---

本指南說明如何運行 **RAG (檢索增強生成)** 系統。這個系統結合了 **MySQL 資料庫的精準度** 與 **Ollama AI 的自然語言能力**，能提供 100% 正確的公差查詢回答。

## 原理
1.  **解析**：程式會分析您的問題 (例如 "25mm H7")。
2.  **檢索**：直接從您的 MySQL 資料庫查詢精確數值。
3.  **生成**：將數值提供給 Ollama，讓 AI 用完整的句子回答您。

## 前置需求
1.  **Python 套件**：
    需要安裝 `ollama` 的 Python 函式庫。
    ```powershell
    pip install ollama sqlalchemy pymysql
    ```

2.  **Ollama 模型**：
    確保您已經安裝 Ollama 並下載了 `llama3` 模型 (或是您微調過的模型)。
    ```powershell
    ollama pull llama3
    ```

## 如何執行
1.  開啟終端機 (Terminal)。
2.  切換到專案目錄：
    ```powershell
    cd C:\Tolerance_Project
    ```
3.  執行 RAG 伺服器：
    ```powershell
    python server/rag_server.py
    ```

## 使用範例
程式啟動後，您可以直接輸入查詢：

```text
User: 幫我查一下 25mm H7 的公差
DEBUG: Detected Size=25.0, Code=H, Grade=IT7
AI: 對於名目尺寸 25mm 的 H7 孔，其公差數據如下：
- 上偏差：+21.0 μm
- 下偏差：0.0 μm

User: 那 50mm h6 呢？
DEBUG: Detected Size=50.0, Code=h, Grade=IT6
AI: 針對 50mm h6 軸，標準公差為：
- 上偏差：0.0 μm
- 下偏差：-16.0 μm
```

## 常見問題
- **Ollama Error**: 如果出現連線錯誤，請確認您的 Ollama 應用程式已經開啟並在背景執行。
- **找不到資料**: 請確認您輸入的格式正確 (數值 + 代號，如 25 H7)，且該數據確實在 Excel/資料庫中。
