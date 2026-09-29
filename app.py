import sys
import configparser
import os,tempfile
from urllib.parse import quote
import copy, json
import re
from pydub import AudioSegment

from flask import Flask, request, abort
import json

from linebot import LineBotApi
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent,
    AudioMessageContent,
    StickerMessageContent,
    PostbackEvent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    MessagingApiBlob,
    FlexMessage,
    FlexContainer,
    AudioMessage,
)

# 讀取其他python檔案
import azure_speech
import azure_translate
import nearby_view_searching
import gemini_reply
import userPre

config = configparser.ConfigParser()
config.read('config.ini')

UPLOAD_FOLDER = 'static'
is_image_uploaded = False


user_states = {} # 用來儲存每個使用者的狀態
user_profiles = {} # 用來儲存每個使用者的行程偏好資料

STATE_DESTINATION = 0   # 問地點
STATE_DAYS = 1          # 問天數
STATE_TRANSPORT = 2     # 問交通
STATE_PREFS = 3         # 問偏好
STATE_CONFIRM = 4       # 確認畫面 (等待輸入 確認 或 修改)
STATE_EDIT = 5          # 修改模式 (正在修改某個欄位)

QUESTIONS = [
    "你想規劃去哪裡旅遊呢？",
    "大約幾天的行程？(請回答幾天幾夜，若為一日遊請回答一天)",
    "你偏好什麼交通方式？（走路 / 大眾運輸 / 開車）",
    "你有什麼偏好嗎？可以一起描述喜歡與不喜歡的事情（要，喜歡什麼 / 不要，討厭什麼 ） 😊"
]

app = Flask(__name__)

channel_access_token = config['Line']['CHANNEL_ACCESS_TOKEN']
channel_secret = config['Line']['CHANNEL_SECRET']
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)

configuration = Configuration(
    access_token=channel_access_token
)

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # parse webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=StickerMessageContent)
def handle_sticker(event):
    user_id = event.source.user_id
    state = user_states.get(user_id)
    reply_msg = []
    if not state:
        reply_msg.append(show_main_function_flex())
        reply_to_user(event.reply_token, reply_msg)


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    state = user_states.get(user_id)
    reply_msg = []

    # ===== 沒有在任何流程 =====
    if not state:
        reply_msg.append(show_main_function_flex())
    
    # ====功能一：等待使用者輸入文字====
    elif state["mode"] == "func1_planning" and state["step"] == "waiting_input":

        asking_state = state["asking_state"]

        if asking_state == STATE_DESTINATION:   
            user_profiles[user_id]["destination"] = user_text
            state["asking_state"] = STATE_DAYS 
            reply_msg.append(TextMessage(text=QUESTIONS[STATE_DAYS]))

        elif asking_state == STATE_DAYS:
            user_profiles[user_id]["days"] = user_text
            state["asking_state"] = STATE_TRANSPORT
            reply_msg.append(TextMessage(text=QUESTIONS[STATE_TRANSPORT]))    

        elif asking_state == STATE_TRANSPORT:
            user_profiles[user_id]["transport"] = user_text
            state["asking_state"] = STATE_PREFS
            reply_msg.append(TextMessage(text=QUESTIONS[STATE_PREFS]))

        elif asking_state == STATE_PREFS:
            # 分析偏好
            like, dislike, neutral = userPre.analyze_preferences(user_text)
            user_profiles[user_id]["preferences"] = {
            "like": like,
            "dislike": dislike,
            "neutral": neutral
        }
            # 這裡不存檔，直接進入確認模式
            state["asking_state"] = STATE_CONFIRM
            reply_msg.append(TextMessage(text=userPre.create_confirmation_message(user_profiles[user_id])))

        #Phase 2: 確認模式 (STATE_CONFIRM)
        elif asking_state == STATE_CONFIRM:
            if user_text == "確認":
                # 1. 寫入檔案
                userPre.save_profile(user_profiles[user_id] , user_id)  
                # 2. 回覆完成
                reply_msg.append(TextMessage(text="已儲存您的行程偏好！開始為您規劃行程..."))
                # reply_to_user(event.reply_token, reply_msg)
                # 3. 呼叫 Gemini 產生行程
                gemini_result = gemini_reply.gemini_llm_sdk(event.message.text, False , True)   #不上傳圖片
                chunks = gemini_reply.split_text(gemini_result)
                # 製作訊息物件列表 (LINE Reply API 最多一次回傳 5 則訊息)
                reply_msg = [TextMessage(text=chunk) for chunk in chunks[:5]]
                # 製作行程各景點的 flex message carousel     
                tourist_locations = parse_itinerary(gemini_result)
                if tourist_locations:
                        flex_json = build_flex_from_json(tourist_locations)
                        reply_msg.append(
                            FlexMessage(
                                alt_text="旅遊行程",
                                contents=FlexContainer.from_json(
                                    json.dumps(flex_json, ensure_ascii=False)
                                )
                            )
                        )
                else:
                    reply_msg.append(TextMessage(text=gemini_result))   
                
                # 清除狀態（流程結束）
                user_states.pop(user_id, None)
                user_profiles.pop(user_id, None)           

            #修改偏好            
            elif user_text.startswith("修改"):
                if "地點" in user_text:
                    user_profiles[user_id]["editing_field"] = "destination"
                    reply_msg.append(TextMessage(text="請輸入新的旅遊地點："))
                    state["asking_state"] = STATE_EDIT
                elif "天數" in user_text:
                    user_profiles[user_id]["editing_field"] = "days"
                    reply_msg.append(TextMessage(text="請輸入新的行程天數："))
                    state["asking_state"] = STATE_EDIT
                elif "交通" in user_text:
                    user_profiles[user_id]["editing_field"] = "transport"
                    reply_msg.append(TextMessage(text="請輸入新的交通方式："))
                    state["asking_state"] = STATE_EDIT
                elif "偏好" in user_text:
                    user_profiles[user_id]["editing_field"] = "preferences"
                    reply_msg.append(TextMessage(text="請重新輸入您的偏好描述："))
                    state["asking_state"] = STATE_EDIT
                else:
                    reply_msg.append(TextMessage(text="不太確定你要修改什麼，請回覆：\n修改旅遊地點、修改行程天數、修改交通方式、或是修改偏好"))
                    state["asking_state"] = STATE_EDIT
            else:
                reply_msg.append(TextMessage(text="請回覆「確認」以儲存，或回覆「修改...」來調整內容。\n\n" + \
                    userPre.create_confirmation_message(user_profiles[user_id])))

        # ==========================================
        # Phase 3: 修改模式 (STATE_EDIT)
        # ==========================================
        elif asking_state == STATE_EDIT:
            field = user_profiles[user_id].get("editing_field")

            if field == "preferences":
                # 偏好需要重新呼叫 Azure 分析
                like, dislike, neutral = userPre.analyze_preferences(user_text)
                user_profiles[user_id]["preferences"] = {
                    "like": like,
                    "dislike": dislike,
                    "neutral": neutral
                }
            else:
                # 一般欄位直接覆蓋
                user_profiles[user_id][field] = user_text

            # 修改完成，清除 editing_field 標記，回到確認狀態
            del user_profiles[user_id]["editing_field"]
            state["asking_state"] = STATE_CONFIRM

            reply_msg.append(TextMessage(text="修改完成！\n\n" + userPre.create_confirmation_message(user_profiles[user_id])))

            

    # ====功能二：等待使用者輸入文字====
    elif state["mode"] == "func2_asking" and state["step"] == "waiting_input":
        gemini_result = gemini_reply.gemini_llm_sdk(event.message.text, is_image_uploaded , False)
        chunks = gemini_reply.split_text(gemini_result)
        # 製作訊息物件列表 (LINE Reply API 最多一次回傳 5 則訊息)
        reply_msg = [TextMessage(text=chunk) for chunk in chunks[:5]]
        user_states.pop(user_id, None)

    # ===== 功能三：等待使用者輸入文字 =====
    elif state["mode"] == "func3_translate" and state["step"] == "waiting_input":
        state["text"] = user_text
        state["step"] = "waiting_language"

        # 這裡回傳「語言選擇 Flex」
        # 假設你有 language_flex.json
        #這裡可能要改成丟function_3_language選單因為上傳語音也會來這裡
        reply_msg.append(flex_message_laguage_choose())
    
    # ===== 功能四：等待使用者輸入搜尋關鍵字 =====
    elif state["mode"] == "func4_searching" and state["step"] == "waiting_input":
        search_result = nearby_view_searching.serp_maps_search(user_text)
        reply_msg.append(TextMessage(text=search_result))
        # 清除狀態（流程結束）
        if not search_result.startswith("找不到結果"):
            user_states.pop(user_id, None)

    else:
        reply_msg.append(TextMessage(text="請依照流程操作"))

    reply_to_user(event.reply_token, reply_msg)

@handler.add(MessageEvent, message=ImageMessageContent)
def message_image(event):
    #要偵測是不是在此功能
    user_id = event.source.user_id
    state = user_states.get(user_id)
    reply_msg = []

    if  state == None or state == None or not state["step"] == "waiting_input" or state["mode"] != "func2_asking":  #   and state["mode"] != "func1_planning"  看功能一要不要上傳圖片，要的話改158 & 159行
        reply_msg.append(TextMessage(text="請在功能二中上傳圖片"))
    else:
        with ApiClient(configuration) as api_client:
            line_bot_blob_api = MessagingApiBlob(api_client)
            message_content = line_bot_blob_api.get_message_content(
                message_id=event.message.id
            )
            with tempfile.NamedTemporaryFile(
                dir=UPLOAD_FOLDER, prefix="", delete=False
            ) as tf:
                tf.write(message_content)
                tempfile_path = tf.name

        original_file_name = os.path.basename(tempfile_path)
        os.replace(
            UPLOAD_FOLDER + "/" + original_file_name,
            UPLOAD_FOLDER + "/" + "output.jpg",
        )

        reply_msg.append(TextMessage(text="上傳完成，你想問關於這張圖片的什麼問題呢？"))

        global is_image_uploaded
        is_image_uploaded = True

    reply_to_user(event.reply_token, reply_msg)

@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    user_id = event.source.user_id
    state = user_states.get(user_id)
    reply_msg = []

    if not state or state["mode"] != "func3_translate" or state["step"] != "waiting_input":
        reply_msg.append(TextMessage(text="請先選擇「功能三：翻譯」再上傳語音"))
        reply_to_user(event.reply_token, reply_msg)
        return

    try:
        # ===== 固定檔名 =====
        m4a_path = os.path.join(UPLOAD_FOLDER, "input.m4a")
        wav_path = os.path.join(UPLOAD_FOLDER, "input.wav")

        # 1️⃣ 下載 LINE 音訊
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            audio_content = blob_api.get_message_content(event.message.id)

        # 2️⃣ 直接覆蓋寫入 input.m4a
        with open(m4a_path, "wb") as f:
            f.write(audio_content)

        # 3️⃣ m4a → wav
        sound = AudioSegment.from_file(m4a_path, format="m4a")
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(wav_path, format="wav")

        # 4️⃣ Azure STT
        recognized_text = azure_speech.azure_stt(wav_path)

        if not recognized_text:
            reply_msg.append(TextMessage(text="❌ 語音辨識失敗，請再試一次"))
        else:
            state["text"] = recognized_text
            reply_msg.append(TextMessage(text=f"🎧 辨識結果：\n{recognized_text}"))
            reply_msg.append(flex_message_laguage_choose())

    except Exception as e:
        reply_msg.append(TextMessage(text=f"發生錯誤：{str(e)}"))

    reply_to_user(event.reply_token, reply_msg)
@handler.add(MessageEvent, message=AudioMessageContent)
def handle_audio_message(event):
    user_id = event.source.user_id
    state = user_states.get(user_id)
    reply_msg = []

    if not state or state["mode"] != "func3_translate" or state["step"] != "waiting_input":
        reply_msg.append(TextMessage(text="請先選擇「功能三：翻譯」再上傳語音"))
        reply_to_user(event.reply_token, reply_msg)
        return

    try:
        # ===== 固定檔名 =====
        m4a_path = os.path.join(UPLOAD_FOLDER, "input.m4a")
        wav_path = os.path.join(UPLOAD_FOLDER, "input.wav")

        # 1️⃣ 下載 LINE 音訊
        with ApiClient(configuration) as api_client:
            blob_api = MessagingApiBlob(api_client)
            audio_content = blob_api.get_message_content(event.message.id)

        # 2️⃣ 直接覆蓋寫入 input.m4a
        with open(m4a_path, "wb") as f:
            f.write(audio_content)

        # 3️⃣ m4a → wav
        sound = AudioSegment.from_file(m4a_path, format="m4a")
        sound = sound.set_frame_rate(16000).set_channels(1)
        sound.export(wav_path, format="wav")

        # 4️⃣ Azure STT
        recognized_text = azure_speech.azure_stt(wav_path)

        if not recognized_text:
            reply_msg.append(TextMessage(text="❌ 語音辨識失敗，請再試一次"))
        else:
            state["text"] = recognized_text
            print(TextMessage(text=f"🎧 辨識結果：\n{recognized_text}"))
            reply_msg.append(flex_message_laguage_choose())

    except Exception as e:
        reply_msg.append(TextMessage(text=f"發生錯誤：{str(e)}"))

    reply_to_user(event.reply_token, reply_msg)


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    reply_msg = []

    # ===== 功能一 =====
    if data == "action=func1":
        user_states[user_id] = {
            "mode": "func1_planning",
            "step": "waiting_input",
            "asking_state" : STATE_DESTINATION,
            "text": None
        }
        user_profiles[user_id] = {}
        reply_msg.append(function_1())

    # ===== 功能二 =====
    elif data == "action=func2":
        user_states[user_id] = {
            "mode": "func2_asking",
            "step": "waiting_input",
            "text": None
        }
        reply_msg.append(function_2())
    # ===== 功能三（完整流程）=====
    elif data == "action=func3":
        # 設定使用者狀態
        user_states[user_id] = {
            "mode": "func3_translate",
            "step": "waiting_input",
            "text": None
        }
        reply_msg.append(function_3_start())

    # ===== 功能三：選擇語言 =====
    elif data.startswith("lang="):
        target_lang = data.split("=")[1]
        state = user_states.get(user_id)

        if not state or state["mode"] != "func3_translate":
            reply_msg = TextMessage(text="請先選擇功能三")
        else:
            translated_result = azure_translate.translate_text(
                state["text"],
                target_lang
            )

            output_filename = "static/output.wav"
            speech_result = azure_speech.azure_tts(
                translated_result,
                target_lang,
                output_filename=output_filename
            )

            # 回傳文字翻譯結果
            reply_msg.append(TextMessage(text="翻譯結果：\n" + translated_result))

            # 回傳語音檔（需提供可被 LINE 存取的 URL 與長度（毫秒））
            if speech_result:
                reply_msg.append(AudioMessage(
                    originalContentUrl=config["Deploy"]["URL"] + "/static/output.wav",
                    duration=speech_result,
                ))  
            else:
                reply_msg.append(TextMessage(text="語音合成失敗"))
            
            # 清除狀態（流程結束）
            user_states.pop(user_id, None)

    # ===== 功能四 =====
    elif data == "action=func4":

        user_states[user_id] = {
            "mode": "func4_searching",
            "step": "waiting_input",
            "text": None
        }
        reply_msg.append(function_4())

    else:
        reply_msg.append(TextMessage(text="未知操作"))

    reply_to_user(event.reply_token, reply_msg)


def function_1():
    return TextMessage(text="開始來幫你規畫行程!" +'\n' + QUESTIONS[STATE_DESTINATION])

def function_2():
    return TextMessage(text="請輸入你想要問的詢問旅遊相關問題或上傳圖片  ex:文化、交通方式等")

def function_3_start():
    # 功能三：語音 / 文字 → 翻譯
    return TextMessage(text="請輸入文字或傳送語音，我會幫你翻譯")

def function_4():
    return TextMessage(text="請輸入你想查詢特定景點附近的店家名稱，例如「台北101附近的咖啡廳」")


def parse_itinerary(text):
    spots = []

    pattern = re.compile(
        r"\*\*(?:上午|下午|午餐|晚餐)：(.+?)\*\*[\s\S]*?"
        r"說明：(.+?)(?:\n|$)"
        r"(?:交通：(.+?))?(?:\n|$)",
        re.MULTILINE
    )

    for match in pattern.findall(text):
        title = match[0].strip()
        desc = match[1].strip()

        spots.append({
            "title": title,
            "description": desc,
        })

    return spots


def build_flex_from_json(spots):
    with open("tourist_attractions.json", "r", encoding="utf-8") as f:
        flex_template = json.load(f)

    bubble_template = flex_template["contents"][0]
    bubbles = []

    for spot in spots[:10]:
        bubble = copy.deepcopy(bubble_template)
        body_contents = bubble["body"]["contents"]

        for item in body_contents:
            if item["type"] == "text" and item["text"] == "{{title}}":
                item["text"] = spot["title"]

            if item["type"] == "box":
                for sub in item["contents"]:
                    if sub["text"] == "{{description}}":
                        sub["text"] = spot["description"]

            if item.get("type") == "button" and item["action"]["type"] == "uri":
                query = quote(spot["title"])
                item["action"]["uri"] = (
                    f"https://www.google.com/maps/search/?api=1&query={query}"
                )


        bubbles.append(bubble)

    return {
        "type": "carousel",
        "contents": bubbles
    }

def flex_message_laguage_choose():
    try:
        with open('language_flex.json', 'r', encoding='utf-8') as f:
            lang_flex = json.load(f)
        laguage_choose_result = (FlexMessage(
            alt_text="選擇翻譯語言",
            contents=FlexContainer.from_json(
                json.dumps(lang_flex, ensure_ascii=False)
            )
        ))
    except Exception:
        laguage_choose_result = (TextMessage(text="語言選單載入失敗"))
    return laguage_choose_result

def reply_to_user(reply_token, reply_msg):
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=reply_msg
            )
        )

def show_main_function_flex():
    try:
        with open('flex_message.json', 'r', encoding='utf-8') as f:
            flex_dict = json.load(f)
        main_function_flex = (FlexMessage(
            alt_text="功能選單",
            contents=FlexContainer.from_json(
                json.dumps(flex_dict, ensure_ascii=False)
            )
        ))
    except Exception:
        main_function_flex = (TextMessage(text="Flex Message 載入失敗"))
    return main_function_flex

#12/24 輸入語音回傳翻譯內容未做完
