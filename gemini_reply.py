import sys
import configparser
import os, tempfile

# Gemini API SDK
import google.generativeai as genai

# image processing
import PIL

from flask import Flask, request, abort
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
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)

#Config Parser
config = configparser.ConfigParser()
config.read('config.ini')

# Gemini API Settings
genai.configure(api_key=config["Gemini"]["API_KEY"])


#讀取txt檔案
def load_llm_role_description(path="llm_original_prompt.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_user_preference(path="userPreference.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

llm_role_description = load_llm_role_description("llm_original_prompt.txt")


# Use the model
from google.generativeai.types import HarmCategory, HarmBlockThreshold
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    safety_settings={
        HarmCategory.HARM_CATEGORY_HARASSMENT:HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH:HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT:HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT:HarmBlockThreshold.BLOCK_NONE,
    },
    generation_config={
        "temperature": 0.4,
        "top_p": 0.85,
        "top_k": 40,
        "max_output_tokens": 8000,
    },
    system_instruction=llm_role_description,
)

UPLOAD_FOLDER = "static"

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


def build_final_user_prompt(preference_text):
    return f"""
以下內容是「使用者已完成填寫的旅遊需求與偏好」，請你【直接依此規劃完整旅遊行程】。

【任務說明】
- 請依據下方需求，規劃完整旅遊行程
- 必須嚴格遵守使用者「不喜歡」的項目
- 請優先滿足「你喜歡」的條件
- 若有衝突，請自行調整並在最後給出簡短說明

【輸出要求】
- 請依 system 指示的 LINE 排版格式輸出
- 請直接輸出結果，不要詢問使用者問題

【使用者需求與偏好】
--------------------------------
{preference_text}
--------------------------------
"""



# --- 切分文字 ---
def split_text(text, max_length=4000):
    return [text[i:i+max_length] for i in range(0, len(text), max_length)]

# --- Gemini LLM SDK 呼叫 ---
def gemini_llm_sdk(user_input, is_image_uploaded ,travel_suggestion):

    user_preference = load_user_preference("userPreference.txt")
    final_prompt = build_final_user_prompt(user_preference)
    try:
        if is_image_uploaded:
            # add image
            upload_image = PIL.Image.open("static/output.jpg")
            response = model.generate_content([user_input, upload_image])
        elif travel_suggestion:
            response = model.generate_content(final_prompt)
        else:
            response = model.generate_content(user_input)
        print(f"Question: {user_input}")
        print(f"Answer: {response.text}")
        return response.text
    except Exception as e:
        print(e)
        return "皆麽奈夫人故障中。"

if __name__ == "__main__":
    app.run()