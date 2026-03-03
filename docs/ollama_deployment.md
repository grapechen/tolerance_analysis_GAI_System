# Ollama 部署指南

> ⚠️ **參考文件** - 此文件為進階功能參考。
> 
> 目前推薦直接使用 Ollama 應用程式，無需手動部署模型。
> 請參考：[cloud_models_guide.md](cloud_models_guide.md)

---

本指南說明如何將您微調後的 GGUF 模型部署到 **Ollama**，讓您可以在本地端與它聊天。

## 前置需求
- 您的電腦已安裝 **Ollama** ([點此下載](https://ollama.com/))。
- `model-unsloth.Q4_K_M.gguf` 檔案 (從 Google Colab 下載的)。

## 第一步：整理檔案
建立一個資料夾 (例如 `C:\Tolerance_Model`) 並將您的 `.gguf` 檔案移動到那裡。

## 第二步：建立 Modelfile
在同一個資料夾中，建立一個名為 `Modelfile` (沒有副檔名) 的文字檔，內容如下：

```dockerfile
FROM ./model-unsloth.Q4_K_M.gguf

# 將溫度 (Temperature) 設低，以獲得符合事實的回答
PARAMETER temperature 0.1

# 設定 System Prompt 來引導模型行為
SYSTEM """
You are a helpful assistant specialized in ISO 286 tolerance standards.
You have access to a specific database of tolerance values.
When asked about a specific size and grade, provide the exact tolerance values from your training data.
If you are unsure, state that you do not have that specific data point.
"""

# 設定對話模板 (Alpaca 格式，需與訓練時一致)
TEMPLATE """
### Instruction:
{{ .Prompt }}

### Response:
"""
```

> [!IMPORTANT]
> 請確保 `FROM` 路徑與您實際的 GGUF 檔名一致。

## 第三步：在 Ollama 中建立模型
開啟您的終端機 (PowerShell 或 Command Prompt)，導航到該資料夾，並執行：

```powershell
cd C:\Tolerance_Model
ollama create tolerance-bot -f Modelfile
```

## 第四步：執行與測試
現在您可以與您的模型聊天了：

```powershell
ollama run tolerance-bot
```

**試試這些問題：**
- "What is the standard tolerance value for a nominal size of 25mm with IT grade IT7?"
- "Find the shaft tolerance deviations for h7 at nominal size 25mm."
