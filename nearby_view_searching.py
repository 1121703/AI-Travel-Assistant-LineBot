import sys
import configparser
import requests

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)

# Config Parser
config = configparser.ConfigParser()
config.read('config.ini')

def detect_language_simple(text: str) -> str:
    """
    超簡易語言偵測（demo 夠用）：
    - 日文：包含假名
    - 韓文：包含韓文字母
    - 英文：包含 a-z
    - 預設：繁體中文 zh-TW
    """
    # Japanese Hiragana/Katakana
    if any('\u3040' <= c <= '\u30ff' for c in text):
        return "ja"
    # Korean Hangul
    if any('\uac00' <= c <= '\ud7af' for c in text):
        return "ko"
    # English letters
    if any(('a' <= c.lower() <= 'z') for c in text):
        return "en"
    return "zh-TW"


def serp_maps_search(user_query: str, limit: int = 5) -> str:
    """
    用 SerpApi 的 google_maps engine 做文字搜尋景點，回傳可直接回覆到 LINE 的文字。
    支援輸入/輸出多語：zh-TW / en / ja / ko（依 user_query 自動切換 hl）
    """
    api_key = config.get("SerpApi", "API_KEY", fallback=None)
    if not api_key:
        return "SerpApi API_KEY 沒設定，請先在 config.ini 加上 [SerpApi] API_KEY"

    lang = detect_language_simple(user_query)

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps",
        "type": "search",
        "q": user_query,
        "hl": lang,
        "api_key": api_key
    }

    title_map = {
        "zh-TW": "🔎 搜尋",
        "en": "🔎 Search",
        "ja": "🔎 検索",
        "ko": "🔎 검색"
    }

    not_found_map = {
        "zh-TW": "找不到結果",
        "en": "No results found",
        "ja": "結果が見つかりません",
        "ko": "결과를 찾을 수 없습니다"
    }

    hint_map = {
        "zh-TW": "你可以換個關鍵字試試（例：台北101 附近景點）",
        "en": "Try another keyword (e.g., 'attractions near Taipei 101')",
        "ja": "別のキーワードで試してみてください（例：台北101 周辺 観光）",
        "ko": "다른 키워드로 시도해보세요 (예: 타이베이 101 근처 관광지)"
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        results = data.get("local_results") or []
        if not results:
            return f"{not_found_map.get(lang, 'No results')}: {user_query}\n{hint_map.get(lang, '')}"

        lines = [f"{title_map.get(lang, '🔎 Search')}: {user_query}"]

        for i, item in enumerate(results[:limit], 1):
            name = item.get("title") or item.get("name") or "（無名稱）"
            rating = item.get("rating")
            reviews = item.get("reviews") or item.get("reviews_count") or item.get("user_ratings_total")
            address = item.get("address") or item.get("formatted_address") or ""

            # ✅ 改：優先使用「景點頁」連結，而不是經緯度
            maps_url = item.get("link")

            if not maps_url:
                place_id = item.get("place_id")
                if place_id:
                    maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}"
                else:
                    gps = item.get("gps_coordinates") or {}
                    lat, lng = gps.get("latitude"), gps.get("longitude")
                    if lat and lng:
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
                    else:
                        q = requests.utils.quote(f"{name} {address}".strip())
                        maps_url = f"https://www.google.com/maps/search/?api=1&query={q}"

            rating_text = f"{rating}⭐" if rating is not None else "N/A"
            if reviews is None:
                reviews_text = ""
            else:
                reviews_text = f"{reviews} 則評論" if lang == "zh-TW" else f"{reviews} reviews"

            addr_text = f"\n   {address}" if address else ""

            if reviews_text:
                lines.append(f"{i}. {name}（{rating_text} {reviews_text}）{addr_text}\n   {maps_url}")
            else:
                lines.append(f"{i}. {name}（{rating_text}）{addr_text}\n   {maps_url}")

        return "\n\n".join(lines)

    except requests.exceptions.RequestException as e:
        return f"SerpApi 連線失敗：{str(e)}"
