# 模型微調指南：公差資料模型

> ⚠️ **參考文件** - 此文件為進階功能參考，專案中未包含相關實作。
> 
> 目前推薦使用 Ollama 應用程式直接使用預訓練模型，無需微調。

---

本指南說明如何使用您生成的公差資料集 (`tolerance_dataset.jsonl`) 來微調 **Llama 3** 模型。我們將使用 **Unsloth**，這是一個能讓微調速度提升 2 倍並減少 60% 記憶體使用的工具，讓您可以在 **免費的 Google Colab** 上運行此流程。

## 前置需求
- 一個 Google 帳號 (用於存取 Google Colab)。
- 一個 Hugging Face 帳號 (用於上傳模型，選用但推薦)。
- 從您的資料庫生成的 `tolerance_dataset.jsonl` 檔案。

## 第一步：開啟 Google Colab
1. 前往 [Google Colab](https://colab.research.google.com/)。
2. 點擊 **新增筆記本 (New Notebook)**。
3. 前往上方選單的 **執行階段 (Runtime)** > **變更執行階段類型 (Change runtime type)**。
4. 選擇 **T4 GPU** (這是免費且足夠使用的)。

## 第二步：安裝依賴套件
複製並貼上以下程式碼到第一個儲存格 (Cell) 並執行：

```python
%%capture
import torch
major_version, minor_version = torch.cuda.get_device_capability()
# 必須分開安裝，因為 Colab 內建的 torch 2.2.1 會導致 unsloth 出錯
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
if major_version >= 8:
    # 適用於較新的 GPU (如 Ampere, Hopper 架構: RTX 30xx, RTX 40xx, A100, H100, L40)
    !pip install --no-deps packaging ninja einops flash-attn xformers trl peft accelerate bitsandbytes
else:
    # 適用於較舊的 GPU (如 V100, Tesla T4, RTX 20xx)
    !pip install --no-deps xformers trl peft accelerate bitsandbytes
pass
```

## 第三步：載入模型與資料集
在新的儲存格中，載入 Llama 3 模型與您的資料集：

```python
from unsloth import FastLanguageModel
import torch

max_seq_length = 2048
dtype = None # None 代表自動偵測。Tesla T4, V100 用 Float16；Ampere+ 用 Bfloat16
load_in_4bit = True # 使用 4bit 量化以減少記憶體用量。也可以設為 False。

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/llama-3-8b-bnb-4bit",
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# 加入 LoRA 適配器 (Adapters)
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # 選擇大於 0 的數字！建議 8, 16, 32, 64, 128
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0, # 支援任意值，但 = 0 最佳化
    bias = "none",    # 支援任意值，但 = "none" 最佳化
    use_gradient_checkpointing = "unsloth", # True 或 "unsloth" (適用於長文本)
    random_state = 3407,
    use_rslora = False,  # 支援 rank stabilized LoRA
    loftq_config = None, # 以及 LoftQ
)

# 載入您的資料集
# 請先將 tolerance_dataset.jsonl 上傳到 Colab 的檔案區！
from datasets import load_dataset
dataset = load_dataset("json", data_files="tolerance_dataset.jsonl", split="train")

# 格式化提示詞 (Prompt)
alpaca_prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
{}

### Input:
{}

### Response:
{}"""

EOS_TOKEN = tokenizer.eos_token # 必須加入 EOS_TOKEN
def formatting_prompts_func(examples):
    instructions = examples["instruction"]
    inputs       = examples["input"]
    outputs      = examples["output"]
    texts = []
    for instruction, input, output in zip(instructions, inputs, outputs):
        # 必須加入 EOS_TOKEN，否則生成會停不下來！
        text = alpaca_prompt.format(instruction, input, output) + EOS_TOKEN
        texts.append(text)
    return { "text" : texts, }

dataset = dataset.map(formatting_prompts_func, batched = True)
```

## 第四步：訓練模型
執行訓練：

```python
from trl import SFTTrainer
from transformers import TrainingArguments

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 2,
    packing = False, # 對於短序列可以讓訓練快 5 倍
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 60, # 根據資料量增加此數值以獲得更好結果 (例如 100-300)
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
        report_to = "none", # <--- 加入這一行來停用 wandb
    ),
)

trainer.train()
```

## 第五步：儲存並匯出為 GGUF (給 Ollama 用)
這是為了讓模型能在 Ollama 上運行的關鍵步驟。

```python
# 儲存為 GGUF 格式
model.save_pretrained_gguf("model", tokenizer, quantization_method = "q4_k_m")
```

執行完畢後，您會在 Colab 的檔案區看到一個名為 `model-unsloth.Q4_K_M.gguf` (或類似名稱) 的檔案。請將此檔案下載到您的電腦。
