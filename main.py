import os
import json
import asyncio
import zipfile
import urllib.request
import subprocess
from aiohttp import web, WSMsgType, ClientSession

# --- ۱. دانلود و آماده‌سازی Xray Core ---
def setup_xray():
    if not os.path.exists("xray"):
        url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
        urllib.request.urlretrieve(url, "xray.zip")
        with zipfile.ZipFile("xray.zip", "r") as zip_ref:
            zip_ref.extractall(".")
        os.chmod("xray", 0o755)

# --- ۲. ساخت کانفیگ داخلی Xray ---
def generate_config():
    uuid = os.environ.get("UUID", "a3b8e7c1-2d4f-4a9b-8c3e-1f2e3d4c5b6a")
    ws_path = os.environ.get("WS_PATH", "/vless-ws")
    
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "port": 10080,
            "listen": "127.0.0.1",
            "protocol": "vless",
            "settings": {
                "clients": [{"id": uuid}],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {"path": ws_path}
            }
        }],
        "outbounds": [{"protocol": "freedom"}]
    }

    with open("config.json", "w") as f:
        json.dump(config, f)

# --- ۳. صفحه نمایش لینک کانفیگ ---
async def handle_panel(request):
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", request.host)
    uuid = os.environ.get("UUID", "a3b8e7c1-2d4f-4a9b-8c3e-1f2e3d4c5b6a")
    ws_path = os.environ.get("WS_PATH", "/vless-ws")
    
    vless_link = f"vless://{uuid}@{domain}:443?type=ws&security=tls&path={ws_path}#Railway-VLESS"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VLESS Config Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; background: #121212; color: #fff; padding-top: 50px; }}
            textarea {{ width: 80%; height: 100px; margin: 20px 0; background: #222; color: #00ffcc; border: 1px solid #444; border-radius: 5px; padding: 10px; font-size: 14px; }}
        </style>
    </head>
    <body>
        <h2>VLESS + WS + TLS Active</h2>
        <p>Copy the configuration link below:</p>
        <textarea readonly>{vless_link}</textarea>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

# --- ۴. پروکسی جابه‌جایی ترافیک WebSocket به Xray ---
async def handle_ws(request):
    ws_path = os.environ.get("WS_PATH", "/vless-ws")
    client_ws = web.WebSocketResponse()
    await client_ws.prepare(request)

    async with ClientSession() as session:
        async with session.ws_connect(f"ws://127.0.0.1:10080{ws_path}") as target_ws:
            
            async def forward_to_target():
                async for msg in client_ws:
                    if msg.type == WSMsgType.BINARY:
                        await target_ws.send_bytes(msg.data)
                    elif msg.type == WSMsgType.TEXT:
                        await target_ws.send_str(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await target_ws.close()
                        break

            async def forward_to_client():
                async for msg in target_ws:
                    if msg.type == WSMsgType.BINARY:
                        await client_ws.send_bytes(msg.data)
                    elif msg.type == WSMsgType.TEXT:
                        await client_ws.send_str(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await client_ws.close()
                        break

            await asyncio.gather(forward_to_target(), forward_to_client())

    return client_ws

if __name__ == "__main__":
    setup_xray()
    generate_config()
    
    # اجرای Xray در پس‌زمینه
    subprocess.Popen(["./xray", "-c", "config.json"])
    
    # ساخت و اجرای وب‌سرور aiohttp
    ws_path = os.environ.get("WS_PATH", "/vless-ws")
    app = web.Application()
    app.router.add_get('/', handle_panel)
    app.router.add_get(ws_path, handle_ws)
    
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host='0.0.0.0', port=port)
    
