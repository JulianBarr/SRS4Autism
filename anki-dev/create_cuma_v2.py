#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import urllib.request
import os
import uuid
import base64
import math
import struct

# --- 关键修复：强制清除代理设置 ---
# 防止 urllib 走 Privoxy/Clash 等代理导致 500 错误
for key in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
    if key in os.environ:
        del os.environ[key]

# --- 配置 ---
ANKI_CONNECT_URL = "http://localhost:8765"
DECK_NAME = "CUMA - Test Deck"
# 与部署脚本保持一致的模型名称
MODEL_NAME = "CUMA-Word-Entity-v2"

# --- 1. 资源生成工具 (SVG图片 + WAV音频) ---

def generate_beep_base64(duration_sec=0.5, freq=440.0, sample_rate=44100):
    """生成简单的正弦波 Beep 音频 (WAV)"""
    num_samples = int(duration_sec * sample_rate)
    audio_data = []
    for i in range(num_samples):
        sample = 32767.0 * math.sin(2.0 * math.pi * freq * i / sample_rate)
        audio_data.append(int(sample))
    packed_data = struct.pack('<' + 'h' * len(audio_data), *audio_data)
    header = struct.pack('<4sI4s', b'RIFF', 36 + len(packed_data), b'WAVE')
    fmt = struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_header = struct.pack('<4sI', b'data', len(packed_data))
    return base64.b64encode(header + fmt + data_header + packed_data).decode('utf-8')

def generate_apple_svg_base64():
    """生成一个红苹果的 SVG 图片"""
    svg_content = """
    <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
      <path d="M100 40 Q130 10 150 40 Q130 70 100 40" fill="green" />
      <circle cx="100" cy="110" r="60" fill="#D32F2F" stroke="#B71C1C" stroke-width="5"/>
      <ellipse cx="80" cy="90" rx="15" ry="10" fill="white" fill-opacity="0.3"/>
      <text x="100" y="190" font-family="Arial" font-size="20" text-anchor="middle" fill="#333">Apple</text>
    </svg>
    """
    return base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')

# --- 2. AnkiConnect 交互逻辑 ---

def invoke(action, **params):
    requestJson = json.dumps({'action': action, 'params': params, 'version': 6}).encode('utf-8')
    req = urllib.request.Request(ANKI_CONNECT_URL, requestJson)
    with urllib.request.urlopen(req) as response:
        result = json.load(response)
        if result.get('error'):
            raise Exception(result['error'])
        return result['result']

def main():
    print(f"🚀 创建 CUMA V2 测试卡片 ({MODEL_NAME})...")

    # 1. 确保存储媒体文件
    print("📦 生成并上传媒体文件...")
    invoke('storeMediaFile', filename="cuma_apple.svg", data=generate_apple_svg_base64())
    invoke('storeMediaFile', filename="cuma_beep.wav", data=generate_beep_base64())

    # 2. 创建或更新 Model (字段分离版)
    model_fields = ["Word", "WordAudio", "WordPicture", "Category", "UUID"]
    
    # 简单的卡片模板 (用于初始化，后续会用 HTML 文件覆盖)
    card_templates = [
        {
            "Name": "Stage 1 - Receptive Easy",
            "Front": "{{WordAudio}}",
            "Back": "{{WordPicture}}"
        },
        {
            "Name": "Stage 2 - Expressive Easy",
            "Front": "{{WordPicture}}",
            "Back": "{{WordAudio}}"
        }
    ]

    try:
        invoke('createDeck', deck=DECK_NAME)
        invoke('createModel', 
               modelName=MODEL_NAME, 
               inOrderFields=model_fields, 
               css=".card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }",
               cardTemplates=card_templates)
        print(f"✅ Model '{MODEL_NAME}' 创建成功")
    except Exception as e:
        print(f"ℹ️ Model 可能已存在，跳过创建: {e}")

    # 3. 添加 Note (使用新字段结构)
    note = {
        "deckName": DECK_NAME,
        "modelName": MODEL_NAME,
        "fields": {
            "Word": "苹果",
            "WordAudio": "cuma_beep.wav", 
            "WordPicture": '<img src="cuma_apple.svg">', 
            "Category": "fruit",
            "UUID": str(uuid.uuid4())
        },
        "options": {"allowDuplicate": True}
    }

    try:
        note_id = invoke('addNote', note=note)
        print(f"✅ 成功添加卡片! ID: {note_id}")
        print("   Word: 苹果")
        print("   Audio: cuma_beep.wav (裸文件名)")
        print("   Picture: <img src='cuma_apple.svg'>")
    except Exception as e:
        print(f"❌ 添加卡片失败: {e}")

if __name__ == "__main__":
    main()
