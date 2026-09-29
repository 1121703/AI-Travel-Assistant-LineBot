
import sys
import re
import configparser
from datetime import datetime
import os


from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import (
    TextAnalyticsClient,
    AnalyzeSentimentAction,
    ExtractKeyPhrasesAction
)

# ========================
# Config
# ========================
config = configparser.ConfigParser()
config.read("config.ini")

credential = AzureKeyCredential(config["AzureLanguage"]["API_KEY"])
text_analytics_client = TextAnalyticsClient(
    endpoint=config["AzureLanguage"]["endpoint"],
    credential=credential
)



# ========================
# 輔助函式：產生確認訊息
# ========================
def create_confirmation_message(profile):
    dest = profile.get("destination", "未設定")
    days = profile.get("days", "未設定")
    trans = profile.get("transport", "未設定")

    # 簡單顯示偏好摘要 (這裡只顯示喜歡/不喜歡的項目數量，避免訊息太長)
    prefs = profile.get("preferences", {})
    like_count = len(prefs.get("like", []))
    dislike_count = len(prefs.get("dislike", []))

    msg = (
        "【行程確認】\n"
        f"📍 地點：{dest}\n"
        f"📅 天數：{days}\n"
        f"🚗 交通：{trans}\n"
        f"💖 偏好分析：喜歡({like_count}) / 不喜歡({dislike_count})\n"
        "-------------------\n"
        "若內容無誤，請回覆「確認」\n"
        "若需修改，請回覆：\n"
        "✏ 修改旅遊地點\n"
        "✏ 修改行程天數\n"
        "✏ 修改交通方式\n"
        "✏ 修改偏好"
    )
    return msg

# ========================
# 偏好分析
# ========================
def analyze_preferences(text: str):
    import re

    # 拆句子
    segments = re.split(r"[，。！？,.!?\n]", text)
    segments = [s.strip() for s in segments if s.strip()]

    if not segments:
        return [], [], []

    poller = text_analytics_client.begin_analyze_actions(
        segments,
        actions=[
            AnalyzeSentimentAction(),
            ExtractKeyPhrasesAction()
        ]
    )

    results = poller.result()

    like, dislike, try_it = [], [], [] # 這裡命名為 try_it 比較清楚，但回傳時對應到原本結構

    for idx, doc in enumerate(results):
        original_text = segments[idx]
        sentiment_result = None
        keyphrases = []

        for r in doc:
            if r.kind == "SentimentAnalysis":
                sentiment_result = r
            elif r.kind == "KeyPhraseExtraction":
                keyphrases = r.key_phrases

        if not sentiment_result:
            continue

        scores = sentiment_result.confidence_scores

        record = {
            "text": original_text,
            "scores": {
                "positive": round(scores.positive, 3),
                "neutral": round(scores.neutral, 3),
                "negative": round(scores.negative, 3),
            },
            "keywords": keyphrases
        }

        # 邏輯判斷
        if scores.positive > scores.neutral and scores.positive > scores.negative:
            # 正向分數最高 -> 喜歡
            like.append(record)
        elif scores.negative > scores.neutral and scores.negative > scores.positive:
            # 負向分數最高 -> 不喜歡
            dislike.append(record)
        else:
            # 中性分數最高 (或平手) -> 歸類為 "或許可以嘗試"
            try_it.append(record)

    # 回傳時，第三個變數對應到外部接收的 neutral
    return like, dislike, try_it

# ========================
# 寫入 userPreference.txt
# ========================
FILE_NAME = "userPreference.txt"

def save_profile(profile , user_id):


    

    if not os.path.exists(FILE_NAME):
        open(FILE_NAME, "w", encoding="utf-8").close()

    remove_old_user_profile(user_id)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(FILE_NAME, "a", encoding="utf-8") as f:

        f.write("====================================\n")
        f.write(f"使用者編號：{user_id}\n")
        f.write(f"建立時間：{timestamp}\n")
        f.write("------------------------------------\n")

        f.write(f"旅遊地點：{profile.get('destination', '')}\n")
        f.write(f"行程天數：{profile.get('days', '')}\n")
        f.write(f"交通方式：{profile.get('transport', '')}\n")

        prefs = profile.get("preferences", {})

        f.write("\n【你喜歡】\n")
        if prefs.get("like"):
            for item in prefs["like"]:
                f.write(f"- {item['text']}\n")
                f.write(f"  關鍵字：{', '.join(item['keywords'])}\n")
                f.write(f"  分數：{item['scores']}\n")
        else:
            f.write("- 無\n")

        f.write("\n【你不喜歡】\n")
        if prefs.get("dislike"):
            for item in prefs["dislike"]:
                f.write(f"- {item['text']}\n")
                f.write(f"  關鍵字：{', '.join(item['keywords'])}\n")
                f.write(f"  分數：{item['scores']}\n")
        else:
            f.write("- 無\n")

        f.write("\n【或許可以嘗試】\n")
        if prefs.get("neutral"):
            for item in prefs["neutral"]:
                f.write(f"- {item['text']}\n")
                f.write(f"  關鍵字：{', '.join(item['keywords'])}\n")
                f.write(f"  分數：{item['scores']}\n")
        else:
            f.write("- 無\n")

        f.write("====================================\n\n")


def remove_old_user_profile(user_id, file_name=FILE_NAME):
    if not os.path.exists(file_name):
        return

    with open(file_name, "r", encoding="utf-8") as f:
        content = f.read()

    # 用使用者編號當區塊切割點
    blocks = content.split("====================================")
    new_blocks = []

    for block in blocks:
        if f"使用者編號：{user_id}" not in block:
            if block.strip():
                new_blocks.append(block.strip())

    # 重寫檔案
    with open(file_name, "w", encoding="utf-8") as f:
        for block in new_blocks:
            f.write("====================================\n")
            f.write(block + "\n")
        if new_blocks:
            f.write("====================================\n\n")
def remove_old_user_profile(user_id, file_name=FILE_NAME):
    if not os.path.exists(file_name):
        return

    with open(file_name, "r", encoding="utf-8") as f:
        content = f.read()

    # 用使用者編號當區塊切割點
    blocks = content.split("====================================")
    new_blocks = []

    for block in blocks:
        if f"使用者編號：{user_id}" not in block:
            if block.strip():
                new_blocks.append(block.strip())

    # 重寫檔案
    with open(file_name, "w", encoding="utf-8") as f:
        for block in new_blocks:
            f.write("====================================\n")
            f.write(block + "\n")
        if new_blocks:
            f.write("====================================\n\n")




