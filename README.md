# 🌍 AI 多語旅遊助理 (Smart Travel Assistant LINE Bot)

> **微型期末專題**  
> 整合 Generative AI、多語系語音辨識/合成、情緒與偏好分析以及周邊景點地圖搜尋的智慧旅遊伴侶 LINE Bot。  
> 📊 **簡報連結**：[Canva 專題簡報](https://canva.link/gpha9idug77pclv)
> 📊 **海報連結**：[Canva 專題海報](https://canva.link/myrizqyqz37sk9z)

---

## 📖 專案簡介

在自由行興盛的時代，旅客常常面臨「行程規劃耗時」、「外語溝通障礙」、「即時周邊探索不便」等痛點。  
本專案開發了一款基於 **LINE Bot** 架構的智慧旅遊助理，結合 **Google Gemini 2.5 Flash**、**Azure AI (Speech, Translator, Language)** 及 **SerpApi (Google Maps)** 等多項雲端 API，提供對話式客製化行程、多模態圖文問答、雙向即時語音翻譯與景點即時查詢的一站式旅遊體驗。

---

## ✨ 核心特色與四大功能

### 1. 🗺️ 智慧行程規劃 (Itinerary Planning)
* **對話式偏好引導**：透過狀態機引導使用者依序輸入目的地、旅遊天數、交通方式與偏好細節。
* **自然語言情緒分析**：利用 **Azure AI Language** 拆解使用者文字，分析正向（喜歡）、負向（排斥）與中性偏好，並抽取出關鍵字儲存為個人偏好檔。
* **客製化生成與確認**：由 **Gemini 2.5 Flash** 針對使用者偏好量身打造行程，並自動將推薦景點轉換成 **LINE Flex Message Carousel (輪播卡片)**，一鍵導引至 Google Maps。

### 2. 💬 多模態旅遊問答 (Travel Q&A)
* **圖文雙模態支援**：支援傳送文字或景點/菜單/路標圖片，由 Gemini 多模態模型進行精準解析。
* **專業旅遊導航員**：提供文化背景解說、特色美食推薦、交通轉乘與突發狀況解答。

### 3. 🌐 即時語音與文字翻譯 (Translation & TTS/STT)
* **多語系跨國溝通**：支援日文、英文、韓文、法文、西班牙文、泰文、繁體中文與簡體中文。
* **語音辨識 (STT)**：透過 LINE 錄音檔轉換（m4a 轉 wav）並經由 **Azure Speech STT** 自動將語音轉為文字。
* **文字轉語音 (TTS)**：翻譯完成後，透過 **Azure Speech TTS** 產生各國在地口音的語音導讀檔，回傳音訊供使用者即時播放溝通。

### 4. 📍 周邊店家與景點搜尋 (Nearby Searching)
* **Google Maps 整合**：串接 **SerpApi Google Maps Engine**。
* **即時關鍵字查詢**：輸入如「台北101附近的咖啡廳」，即時回傳評分、評論數、地址與 Google 地圖詳細連結。
* **多語系自動相容**：自動辨識使用者輸入語言（中、英、日、韓），回傳相應語系結果。

---

## 🛠️ 系統架構與技術棧

### 系統架構圖

```
                 +-----------------------------------+
                 |           LINE App User           |
                 +-----------------+-----------------+
                                   | (Webhook / Reply)
                                   v
+-------------------------------------------------------------------------+
|                           Flask Web Server                              |
|                              (app.py)                                   |
|                                                                         |
|  +-------------------+  +-------------------+  +---------------------+  |
|  | State & Profile   |  | Multi-format Msg  |  | Audio Processing    |  |
|  | Management        |  | (Flex/Carousel)   |  | (pydub / librosa)   |  |
|  +---------+---------+  +---------+---------+  +----------+----------+  |
+------------|----------------------|-----------------------|-------------+
             |                      |                       |
             v                      v                       v
    +-----------------+    +-----------------+    +-------------------+
    | Google Gemini   |    | SerpApi         |    | Azure Cognitive   |
    | 2.5 Flash       |    | (Google Maps)   |    | Services          |
    | - 行程規劃      |    | - 景點周邊檢索  |    | - Speech STT/TTS  |
    | - 旅遊問答/視覺 |    |                 |    | - Translator API  |
    +-----------------+    +-----------------+    | - Language (情緒) |
                                                  +-------------------+
```

### 技術使用

* **後端框架**：Python 3.10+、Flask
* **通訊協定與平台**：LINE Messaging API SDK v3 (WebhookHandler, Flex Message, AudioMessage)
* **生成式 AI**：Google Generative AI SDK (`gemini-2.5-flash`)
* **微軟認知服務**：
  * Azure Cognitive Services Speech (語音轉文字 STT、文字轉語音 TTS)
  * Azure Translator API (文字多語系翻譯)
  * Azure AI Text Analytics / Language Service (情緒分析與關鍵字擷取)
* **地圖檢索**：SerpApi (Google Maps Engine)
* **音訊處理**：pydub、librosa、ffmpeg
* **部署與穿透**：ngrok

---

## 📂 專案檔案結構

```bash
├── app.py                      # Flask 主伺服器與 LINE Webhook 事件處理
├── gemini_reply.py             # Gemini 模型串接、Prompt 模板與回應切分
├── azure_speech.py             # Azure Speech STT (語音辨識) 與 TTS (語音合成)
├── azure_translate.py          # Azure Translator API 文字翻譯邏輯
├── userPre.py                  # Azure Language 情緒與關鍵字分析、偏好檔案讀寫
├── nearby_view_searching.py    # SerpApi Google Maps 周邊景點查詢
├── flex_message.json           # 主功能清單 Flex Message 模板
├── language_flex.json          # 翻譯目標語言選擇 Flex Message 模板
├── tourist_attractions.json    # 行程景點 Carousel 輪播 Flex Message 模板
├── llm_original_prompt.txt     # Gemini 角色設定與系統提示詞 (System Prompt)
├── userPreference.txt          # 使用者旅遊偏好記錄檔
├── config.ini                  # API 金鑰與環境變數設定檔 (需要自己建立)
├── requirements.txt            # Python 相依套件清單
└── static/                     # 存放暫存之音訊檔 (output.wav) 與上傳圖片
```

---

## 🚀 快速開始

### 1. 環境準備
請確認已安裝 Python 3.10 以上版本，並安裝系統級音訊套件 `ffmpeg`。

### 2. 安裝相依套件
```bash
pip install -r requirements.txt
```

> **`requirements.txt` 內容參考：**
> ```text
> flask
> line-bot-sdk
> google-generativeai
> azure-cognitiveservices-speech
> azure-ai-textanalytics
> requests
> pillow
> pydub
> librosa
> ```

### 3. 設定 `config.ini`
在專案根目錄下建立或編輯 `config.ini`：

```ini
[Line]
CHANNEL_ACCESS_TOKEN = YOUR_LINE_CHANNEL_ACCESS_TOKEN
CHANNEL_SECRET = YOUR_LINE_CHANNEL_SECRET

[Speech]
key = YOUR_AZURE_SPEECH_KEY
region = YOUR_AZURE_SPEECH_REGION

[Translator]
key = YOUR_AZURE_TRANSLATOR_KEY
region = YOUR_AZURE_TRANSLATOR_REGION
endpoint = https://api.cognitive.microsofttranslator.com/

[AzureLanguage]
API_KEY = YOUR_AZURE_LANGUAGE_KEY
endpoint = YOUR_AZURE_LANGUAGE_ENDPOINT

[SerpApi]
API_KEY = YOUR_SERPAPI_KEY

[Deploy]
URL = YOUR_NGROK_OR_DOMAIN_URL

[Gemini]
API_KEY = YOUR_GEMINI_API_KEY
```

### 4. 啟動伺服器與 Webhook
```bash
# 啟動 Flask 服務
python app.py
```

開啟 ngrok 進行外部公開穿透：
```bash
ngrok http 5000
```
將產生的 ngrok 網址複製並填入：
1. `config.ini` 中的 `[Deploy]` -> `URL`。
2. LINE Developers Console 中的 Webhook URL：`https://<your-ngrok-url>/callback`。

---

## 📱 示範流程

1. **功能選單**：傳送貼圖或輸入任意文字叫出 4 大功能主選單。
2. **行程規劃**：點選「行程規劃」，依序輸入景點、天數、交通方式與詳細喜好，系統自動建立偏好分析並生成可視化輪播卡片。
3. **旅遊問答**：上傳異國景點或菜單照片，詢問背景或推薦菜色。
4. **即時翻譯**：傳送文字或語音訊息，挑選目標語言後即可同步收到文字譯文與語音朗讀。
5. **周邊搜尋**：輸入「[地點] 附近的 [類別]」，即時取得 Google Maps 評分與地標連結。

---

## 👥 專案貢獻與期末成果

* **簡報展示**：[點擊此處瀏覽 Canva 專案簡報](https://canva.link/gpha9idug77pclv)
* 本專案為微型期末專案，整合各項前瞻生成式 AI 與認知 API，驗證了對話式 AI 在智慧觀光旅遊場景的實際落地效益。
