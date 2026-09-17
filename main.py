import os
import json
import asyncio
import zipfile
import base64
import urllib.parse
import urllib.request
import subprocess
from aiohttp import web, WSMsgType, ClientSession

# --- ۱. دانلود و نصب Xray Core ---
def setup_xray():
    if not os.path.exists("xray"):
        url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
        urllib.request.urlretrieve(url, "xray.zip")
        with zipfile.ZipFile("xray.zip", "r") as zip_ref:
            zip_ref.extractall(".")
        os.chmod("xray", 0o755)

# --- ۲. ساخت کانفیگ همزمان برای ۴ پروتکل در Xray ---
def generate_config():
    uuid = os.environ.get("UUID", "a3b8e7c1-2d4f-4a9b-8c3e-1f2e3d4c5b6a")
    ws_path = os.environ.get("WS_PATH", "/dragon")
    password = os.environ.get("PASSWORD", "dragonpass123")
    # کلید ۱۶ بایتی Base64 استاندارد برای Shadowsocks 2022
    ss_key = os.environ.get("SS_KEY", "uO1/q1R2O4L5e6P7r8S9t0==")
    
    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            # 1. VLESS
            {
                "port": 10080,
                "listen": "127.0.0.1",
                "protocol": "vless",
                "settings": {"clients": [{"id": uuid}], "decryption": "none"},
                "streamSettings": {"network": "ws", "wsSettings": {"path": ws_path}}
            },
            # 2. VMess
            {
                "port": 10081,
                "listen": "127.0.0.1",
                "protocol": "vmess",
                "settings": {"clients": [{"id": uuid, "alterId": 0}]},
                "streamSettings": {"network": "ws", "wsSettings": {"path": f"{ws_path}-vmess"}}
            },
            # 3. Trojan
            {
                "port": 10082,
                "listen": "127.0.0.1",
                "protocol": "trojan",
                "settings": {"clients": [{"password": password}]},
                "streamSettings": {"network": "ws", "wsSettings": {"path": f"{ws_path}-trojan"}}
            },
            # 4. Shadowsocks
            {
                "port": 10083,
                "listen": "127.0.0.1",
                "protocol": "shadowsocks",
                "settings": {
                    "method": "2022-blake3-aes-128-gcm",
                    "password": ss_key,
                    "network": "tcp,udp"
                },
                "streamSettings": {"network": "ws", "wsSettings": {"path": f"{ws_path}-ss"}}
            }
        ],
        "outbounds": [{"protocol": "freedom"}]
    }

    with open("config.json", "w") as f:
        json.dump(config, f)

# --- ۳. ساخت پنل وب با تمام لینک‌ها ---
async def handle_panel(request):
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", request.host)
    uuid = os.environ.get("UUID", "a3b8e7c1-2d4f-4a9b-8c3e-1f2e3d4c5b6a")
    ws_path = os.environ.get("WS_PATH", "/dragon")
    password = os.environ.get("PASSWORD", "dragonpass123")
    ss_key = os.environ.get("SS_KEY", "uO1/q1R2O4L5e6P7r8S9t0==")
    
    encoded_path = urllib.parse.quote(ws_path, safe='')
    
    # ۱. لینک VLESS با فرمت کامل دقیق
    vless_link = f"vless://{uuid}@{domain}:443?path={encoded_path}&security=tls&alpn=h2&encryption=none&insecure=0&host={domain}&fp=chrome&type=ws&allowInsecure=0&sni={domain}#Railway-VLESS"
    
    # ۲. لینک VMess
    vmess_dict = {
        "v": "2", "ps": "Railway-VMess", "add": domain, "port": "443",
        "id": uuid, "aid": "0", "scy": "auto", "net": "ws",
        "type": "none", "host": domain, "path": f"{ws_path}-vmess", "tls": "tls", "sni": domain
    }
    vmess_link = "vmess://" + base64.b64encode(json.dumps(vmess_dict).encode()).decode()

    # ۳. لینک Trojan
    encoded_trojan_path = urllib.parse.quote(f"{ws_path}-trojan", safe='')
    trojan_link = f"trojan://{password}@{domain}:443?path={encoded_trojan_path}&security=tls&alpn=h2&host={domain}&fp=chrome&type=ws&sni={domain}#Railway-Trojan"

    # ۴. لینک Shadowsocks + WS + TLS
    encoded_ss_path = urllib.parse.quote(f"{ws_path}-ss", safe='')
    user_info = base64.b64encode(f"2022-blake3-aes-128-gcm:{ss_key}".encode()).decode()
    ss_link = f"ss://{user_info}@{domain}:443?type=ws&path={encoded_ss_path}&security=tls&host={domain}&sni={domain}#Railway-Shadowsocks"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multi-Protocol Config Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; background: #0f172a; color: #f8fafc; padding: 20px; }}
            .box {{ background: #1e293b; margin: 15px auto; padding: 15px; width: 85%; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            h3 {{ color: #38bdf8; margin-top: 0; margin-bottom: 10px; font-size: 16px; }}
            textarea {{ width: 100%; height: 60px; background: #0f172a; color: #4ade80; border: 1px solid #334155; border-radius: 5px; padding: 8px; font-size: 12px; resize: none; word-break: break-all; }}
        </style>
    </head>
    <body>
        <h2>Multi-Protocol Node Panel</h2>
        
        <div class="box">
            <h3>VLESS + WS + TLS</h3>
            <textarea readonly>{vless_link}</textarea>
        </div>

        <div class="box">
            <h3>VMess + WS + TLS</h3>
            <textarea readonly>{vmess_link}</textarea>
        </div>

        <div class="box">
            <h3>Trojan + WS + TLS</h3>
            <textarea readonly>{trojan_link}</textarea>
        </div>

        <div class="box">
            <h3>Shadowsocks + WS + TLS</h3>
            <textarea readonly>{ss_link}</textarea>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

# --- ۴. هدایت اتصالات WS به پورت مرتبط در Xray ---
async def handle_ws(request):
    ws_path = os.environ.get("WS_PATH", "/dragon")
    path = request.path
    
    target_port = 10080
    if path == f"{ws_path}-vmess":
        target_port = 10081
    elif path == f"{ws_path}-trojan":
        target_port = 10082
    elif path == f"{ws_path}-ss":
        target_port = 10083

    client_ws = web.WebSocketResponse()
    await client_ws.prepare(request)

    async with ClientSession() as session:
        async with session.ws_connect(f"ws://127.0.0.1:{target_port}{path}") as target_ws:
            
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
    
    subprocess.Popen(["./xray", "-c", "config.json"])
    
    ws_path = os.environ.get("WS_PATH", "/dragon")
    app = web.Application()
    app.router.add_get('/', handle_panel)
    
    # ثبت مسیر تمامی پروتکل‌ها
    app.router.add_get(ws_path, handle_ws)
    app.router.add_get(f"{ws_path}-vmess", handle_ws)
    app.router.add_get(f"{ws_path}-trojan", handle_ws)
    app.router.add_get(f"{ws_path}-ss", handle_ws)
    
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host='0.0.0.0', port=port)
    
