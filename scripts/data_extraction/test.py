import os
import requests

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("⚠️ 未找到 GEMINI_API_KEY")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

proxies = {
    "http": "http://127.0.0.1:1087",
    "https": "http://127.0.0.1:1087"
}

payload = {
    "contents": [{"parts": [{"text": "Ping! 如果收到，请只回复 Pong。"}]}]
}

# 🛡️ 祭出法宝：创建一个会话，并强制它无视终端的环境变量！
session = requests.Session()
session.trust_env = False  # <--- 核心魔法就在这一句

print("🌐 正在开启绝对隔离模式，通过 HTTP 代理 (1087) 向 Google 发送探路信号...")

try:
    # 注意这里改成了 session.post
    response = session.post(url, json=payload, proxies=proxies, timeout=15)
    
    if response.status_code == 200:
        reply = response.json()['candidates'][0]['content']['parts'][0]['text']
        print(f"✅ 链路畅通无阻！大模型回复: {reply.strip()}")
        print("👉 代理终于通了！赶紧去跑 PDF 提取大招！")
    else:
        print(f"❌ 连上了，但被拒绝了。状态码: {response.status_code}")
        print(response.text)
        
except Exception as e:
    print(f"❌ 链路依然超时，诊断信息:\n{e}")
    print("\n⚠️ 架构师警告：如果加上 trust_env=False 还是超时，说明 1087 通了，但是你的 VPN 节点被 Google 拦截或节点本身太慢了！")
    print("👉 解决方案：点击 Mac 右上角的小飞机，切换一个 VPN 节点（比如从香港切到美国、日本或台湾），然后重试！")
