import asyncio
import websockets
import json
import http.server
import socketserver
import threading

# 使用全新的端口，彻底避开 8000 和 8765 冲突
HTTP_PORT = 8088
WS_PORT = 8777

def start_http_server():
    Handler = http.server.SimpleHTTPRequestHandler
    # 允许端口复用，防止重启脚本时报错 Address already in use
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", HTTP_PORT), Handler) as httpd:
        print("===================================================")
        print(f"🌍 HTTP Server 运行在: http://localhost:{HTTP_PORT}")
        print(f"📱 手机端 (方舟反应炉) 请访问: http://[你的Mac局域网IP]:{HTTP_PORT}")
        print(f"💻 Mac端 (视觉控制台) 请访问: http://localhost:{HTTP_PORT}/mac.html")
        print("===================================================")
        httpd.serve_forever()

clients = set()

async def ws_handler(websocket):
    clients.add(websocket)
    try:
        async for message in websocket:
            # 收到 Mac 端发来的数据，直接广播给所有连上的手机
            for client in clients:
                if client != websocket:
                    await client.send(message)
    finally:
        clients.remove(websocket)

async def start_ws_server():
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        print(f"📡 WebSocket 信号塔就绪，监听端口: {WS_PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    # 在独立线程跑 HTTP，主线程跑 WebSocket
    threading.Thread(target=start_http_server, daemon=True).start()
    asyncio.run(start_ws_server())
