# ISO 286 RAG 系統說明文件

這份文件詳細說明了我們為何選擇 **RAG (檢索增強生成)** 架構來建置公差查詢助手，以及該系統的運作原理與使用步驟。

## 1. 為什麼選擇 RAG 而不是微調 (Fine-tuning)？

在建置專業知識 (如 ISO 286 公差) 的 AI 助手時，RAG 通常是比微調更好的選擇，原因如下：

| 特性 | RAG (檢索增強生成) | Fine-tuning (模型微調) |
| :--- | :--- | :--- |
| **準確度** | **極高**。AI 直接閱讀資料庫中的正確數值回答，不會算錯。 | **中等**。AI 靠「背誦」數據，容易記錯或產生幻覺 (胡說八道)。 |
| **數據更新** | **即時**。只要更新 Excel/資料庫，AI 馬上知道新數據。 | **困難**。每次數據更新都需要重新訓練模型 (耗時、耗算力)。 |
| **可解釋性** | **高**。我們可以知道 AI 是根據哪一筆資料回答的。 | **低**。AI 的回答來自神經網路內部的權重，難以追溯來源。 |
| **成本** | **低**。不需要昂貴的 GPU 進行訓練。 | **高**。需要租用 GPU 或購買高階顯卡進行訓練。 |

**結論：**
對於公差查詢這種**「絕對不能出錯」**且**「數值精確」**的任務，RAG 是最合適的解決方案。微調 (Fine-tuning) 更適合用於改變 AI 的說話風格或學習特定的程式語言格式，而不是用來背誦數據表。

---

## 2. 系統架構與運作原理

我們的 RAG 系統 (`rag_server.py`) 運作流程如下：

1.  **用戶提問 (User Query)**
    *   例如：「25mm H7」或「分析 25mm H7/h6」

2.  **意圖解析 (Intent Parsing)**
    *   系統使用正則表達式 (Regex) 分析用戶輸入。
    *   提取關鍵字：尺寸 (`25mm`)、孔公差 (`H7`)、軸公差 (`h6`)。

3.  **資料檢索 (Data Retrieval)**
    *   系統根據提取的關鍵字，直接查詢 MySQL 資料庫 (`iso286_tolerance`, `hole_tolerance`, `shaft_tolerance`)。
    *   如果是配合分析，會同時查詢孔與軸的數據，並計算間隙/過盈數值。

4.  **提示詞增強 (Prompt Augmentation)**
    *   系統將**用戶的問題**與**查到的正確數據**組合成一個詳細的提示詞 (Prompt)。
    *   *Prompt 範例：* 「用戶問 25mm H7。資料庫顯示：上偏差 +21um，下偏差 0um。請用這些數據回答用戶。」

5.  **AI 生成回答 (Generation)**
    *   將組合好的提示詞傳送給 **Ollama (Llama 3 模型)**。
    *   AI 根據提示詞，用自然語言生成最終的回答。

---

## 3. Ollama 的角色與互動機制

### Ollama 的角色
在這個系統中，Ollama 扮演的是 **「推理引擎 (Inference Engine)」** 的角色。
*   它**不負責**儲存公差數據 (數據在 MySQL 資料庫裡)。
*   它**只負責**「說話」和「理解上下文」。
*   它就像是一個**大腦**，我們把資料庫查到的**知識** (公差數值) 餵給它，請它用流暢的中文講給用戶聽。

### 系統如何「截獲」與使用 Ollama？
我們的 Python 程式 (`rag_server.py`) 透過 **API (應用程式介面)** 與 Ollama 進行溝通。具體流程如下：

1.  **建立連線**：
    *   Python 使用 `import ollama` 函式庫。
    *   Ollama 在背景執行一個 HTTP 伺服器 (預設 Port 11434)。

2.  **發送請求 (Request)**：
    *   Python 將組合好的 **Prompt (提示詞)** 打包成一個 JSON 格式的訊息。
    *   透過 API 發送給 Ollama，指定使用 `llama3.1:8b` 模型。
    *   *程式碼範例：*
        ```python
        response = ollama.chat(model='llama3.1:8b', messages=[
            {'role': 'user', 'content': prompt}
        ])
        ```

3.  **截獲回應 (Intercept Response)**：
    *   Ollama 計算完畢後，會回傳一個 JSON 物件。
    *   Python 程式「截獲」這個物件，並提取其中的 `content` 欄位 (即 AI 的文字回答)。
    *   最後將這段文字顯示在網頁上給用戶看。

---

## 4. 深入了解 Ollama 應用程式

Ollama 不僅僅是一個後端服務，它本身是一個強大的**本地大語言模型管理工具**。

### 它的核心功能
1.  **模型託管 (Model Hosting)**：
    *   它像一個網頁伺服器 (Web Server)，但託管的是 AI 模型。
    *   它讓您的 Python 程式可以像呼叫 OpenAI API 一樣呼叫本地的模型。

2.  **模型管理 (Model Management)**：
    *   就像 Docker 管理容器一樣，Ollama 管理您的 AI 模型。
    *   `ollama pull`: 下載模型 (如 llama3, mistral, gemma)。
    *   `ollama list`: 查看已安裝的模型。
    *   `ollama rm`: 刪除不用的模型以釋放空間。

3.  **直接互動 (Direct Interaction)**：
    *   您可以在終端機直接輸入 `ollama run llama3.1:8b` 來跟 AI 聊天，這在測試模型本身能力時非常有用 (不經過我們的 RAG 系統)。

### 在本專案中的進階應用
雖然我們目前只用它來跑 Llama 3，但您可以隨時透過 Ollama 升級您的專案：

*   **更換更強的模型**：
    *   如果未來 Llama 4 出來了，您只需要 `ollama pull llama4`，然後修改 `rag_server.py` 裡的一行程式碼，您的系統就立刻升級了！
*   **嘗試不同風格的模型**：
    *   您可以下載 `gemma` (Google 的模型) 或 `mistral`，比較看看誰解釋公差比較清楚。
*   **自定義模型 (Modelfile)**：
    *   您可以創建一個 `Modelfile`，鎖定 System Prompt (例如：「你是一個講話很幽默的工程師」)，然後建立一個專屬模型 `ollama create my-engineer -f Modelfile`。

---

## 5. 詳細使用步驟

### 前置準備
確保您已經完成以下事項：
1.  安裝並啟動 **Ollama**。
2.  下載模型：`ollama pull llama3.1:8b`。
3.  資料庫已建立並匯入 Excel 資料 (`import_all_data.py`)。

### 啟動系統
我們已經將 RAG 系統整合到網頁伺服器中，您只需要啟動網頁伺服器即可。

1.  開啟終端機 (Terminal)。
2.  進入專案目錄並啟動虛擬環境。
3.  執行伺服器：
    ```powershell
    python server/app.py
    ```

### 使用方式
1.  打開瀏覽器，前往 `http://127.0.0.1:7010`。
2.  點擊上方的 **「AI 助手」** 分頁。
3.  在對話框輸入您的問題：

    *   **單一公差查詢**：
        *   輸入：「25mm H7」
        *   輸入：「查一下 50mm g6 的公差」
    
    *   **配合分析**：
        *   輸入：「分析 25mm H7/h6」
        *   輸入：「40mm H7 配 g6 是什麼配合？」

### 常見問題排除
*   **AI 回答 "Ollama Error"**：
    *   請確認 Ollama 應用程式已開啟。
    *   請確認已執行 `ollama pull llama3.1:8b` 下載模型。
*   **網頁沒反應**：
    *   請按 `Ctrl + F5` 強制重新整理網頁。
    *   檢查終端機是否有錯誤訊息。
