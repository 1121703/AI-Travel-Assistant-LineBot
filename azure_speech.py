import azure.cognitiveservices.speech as speechsdk
import configparser
import os
import librosa

# 1. 初始化 ConfigParser
config = configparser.ConfigParser()
config.read('config.ini')

# 2. 取得 Azure Speech 設定
try:
    speech_key = config['Speech']['key']
    service_region = config['Speech']['region']
except KeyError:
    print("錯誤: config.ini 中找不到 Speech 設定")
    speech_key, service_region = None, None

# === [核心資料] 語言設定總表 ===
LANGUAGE_MENU = {
    "1": {"name": "日文", "code": "ja", "voice": "ja-JP-NanamiNeural"},
    "2": {"name": "英文", "code": "en", "voice": "en-US-AvaNeural"},
    "3": {"name": "韓文", "code": "ko", "voice": "ko-KR-SunHiNeural"},
    "4": {"name": "法文", "code": "fr", "voice": "fr-FR-DeniseNeural"},
    "5": {"name": "西班牙文", "code": "es", "voice": "es-ES-ElviraNeural"},
    "6": {"name": "泰文", "code": "th", "voice": "th-TH-PremwadeeNeural"},
    "7": {"name": "中文(台灣)", "code": "zh-Hant", "voice": "zh-TW-HsiaoChenNeural"},
    "8": {"name": "中文(大陸)", "code": "zh-Hans", "voice": "zh-CN-XiaoxiaoNeural"}
}

def azure_stt(audio_filename):
    """語音轉文字 (STT)"""
    if not speech_key: return None

    try:
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.speech_recognition_language = "zh-TW"
        
        audio_config = speechsdk.audio.AudioConfig(filename=audio_filename)
        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        print(f"正在辨識檔案: {audio_filename} ...")
        result = speech_recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return "無法辨識語音"
        elif result.reason == speechsdk.ResultReason.Canceled:
            return f"辨識取消: {result.cancellation_details.reason}"
            
    except Exception as e:
        print(f"STT 錯誤: {e}")
        return None

def azure_tts(text, language_code, output_filename="static/output.wav"):
    """
    文字轉語音 (TTS)
    參數:
      - output_filename: 預設為 'static/output.wav' (每次呼叫都會覆蓋此檔)
    """
    if not speech_key: return None

    # 1. 確保 static 資料夾存在
    if not os.path.exists('static'):
        os.makedirs('static')

    # 2. 根據 language_code 找出對應的 voice name
    target_voice = "en-US-AvaNeural" # 預設值
    for key, info in LANGUAGE_MENU.items():
        if info['code'] == language_code:
            target_voice = info['voice']
            break

    try:
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.speech_synthesis_voice_name = target_voice
        
        print(f"TTS 合成設定: 語言碼={language_code}, 角色={target_voice}, 檔名={output_filename}")

        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_filename)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"語音合成成功: {output_filename}")
            
            audio_duration = round(
                librosa.get_duration(path=output_filename) * 1000
            )
            return audio_duration
        else:
            print(f"語音合成失敗: {result.cancellation_details.reason}")
            return None
            
    except Exception as e:
        print(f"TTS 錯誤: {e}")
        return None