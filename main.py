import json
import os
import subprocess
import urllib.request
import zipfile
from flask import Flask

app = Flask(__name__)

# دانلود و نصب Xray Core در صورت عدم وجود
def setup_xray():
    if not os.path.exists("xray"):
        url = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
        urllib.request.urlretrieve(url, "xray.zip")
        with zipfile.ZipFile("xray.zip", "r") as zip_ref:
            zip_ref.extractall(".")
        os.chmod("xray", 0o755)

# ساخت کانفیگ Xray
def generate_config():
    port = int(os.environ.get("PORT", 8080))
    uuid = os.environ.get("UUID", "a3b8e7c1-2d4f-4a9b-8c3e-1f2e3d4c5b6a")
    path = os.environ.get("WS_PATH", "/vless-ws")

    config = {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "port": port,
                "protocol": "vless",
                "settings": {
                    "clients": [{"id": uuid, "level": 0}],
                    "decryption": "none"
                },
                "streamSettings": {
                    "network": "ws",
                    "wsSettings": {"path": path}
                }
            }
        ],
        "outbounds": [{"protocol": "freedom"}]
    }

    with open("config.json", "w") as f:
        json.dump(config, f)

@app.route("/")
def home():
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "YOUR-APP.up.railway.app")
    uuid = os.environ.get("UUID", "a3b8e7c1-2d4f-4a9b-8c3e-1f2e3d4c5b6a")
    path = os.environ.get("WS_PATH", "/vless-ws")
    
    # ساخت لینک vless
    vless_link = f"vless://{uuid}@{domain}:443?type=ws&security=tls&path={path}#Railway-VLESS"

    return f"""
    <html>
        <head><title>VLESS Panel</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background-color: #f4f4f9;">
            <h2>VLESS + WS + TLS Configuration</h2>
            <p><strong>Domain:</strong> {domain}</p>
            <textarea style="width: 80%; height: 100px; margin-top: 10px;">{vless_link}</textarea>
        </body>
    </html>
    """

if __name__ == "__main__":
    setup_xray()
    generate_config()
    # اجرای Xray در پس‌زمینه
    subprocess.Popen(["./xray", "-c", "config.json"])
    # اجرای برنامه Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
