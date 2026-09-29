import requests
import uuid
import configparser
import os

# 1. 初始化 ConfigParser
config = configparser.ConfigParser()
config.read('config.ini')

try:
    key = config['Translator']['key']
    region = config['Translator']['region']
    endpoint = config['Translator']['endpoint']
except KeyError as e:
    print(f"錯誤: config.ini 中找不到 {e} 設定")
    key, region, endpoint = None, None, None

def translate_text(text, target_language):
    if not key or not region:
        return "錯誤：伺服器設定檔讀取失敗"

    path = '/translate'
    constructed_url = endpoint + path

    params = {
        'api-version': '3.0',
        # 'from': 'zh-Hant', # 已移除，讓 Azure 自動偵測來源語言
        'to': [target_language]
    }

    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Ocp-Apim-Subscription-Region': region,
        'Content-type': 'application/json',
        'X-ClientTraceId': str(uuid.uuid4())
    }

    body = [{'text': text}]

    try:
        request = requests.post(constructed_url, params=params, headers=headers, json=body)
        response = request.json()
        
        if 'error' in response:
            print(f"API Error: {response}")
            return None
            
        translated_text = response[0]['translations'][0]['text']
        return translated_text
        
    except Exception as e:
        print(f"翻譯連線錯誤: {e}")
        return None