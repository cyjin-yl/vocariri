"""Synthetic image repro; no PV media or private infrastructure required.

Usage: python vision-repro.py http://localhost:8000 [redacted model]
Requires Pillow. If authentication is needed, enter an API key at the prompt.
"""
import base64
import getpass
import io
import json
import sys
import urllib.request
import uuid

from PIL import Image, ImageDraw

base_url, model = sys.argv[1:3]
image = Image.new("RGB", (512, 384), "white")
draw = ImageDraw.Draw(image)
draw.rectangle((30, 60, 210, 240), fill="red")
draw.ellipse((300, 60, 480, 240), fill="blue")
draw.text((180, 300), "PV731", fill="black", font_size=48)
buffer = io.BytesIO()
image.save(buffer, format="PNG")
image.save("vision-control.png")
payload = {
    "model": model,
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Describe the shapes, colors and text visible in this image."},
        {"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
        }},
    ]}],
    "temperature": 0,
    "max_tokens": 200,
    "chat_template_kwargs": {"enable_thinking": False},
    "cache_salt": uuid.uuid4().hex,
}
headers = {"Content-Type": "application/json"}
key = getpass.getpass("API key (leave blank if not required): ")
if key:
    headers["Authorization"] = "Bearer " + key
request = urllib.request.Request(
    base_url.rstrip("/") + "/v1/chat/completions",
    data=json.dumps(payload).encode(), headers=headers,
)
with urllib.request.urlopen(request, timeout=180) as response:
    result = json.load(response)
print(json.dumps(result, ensure_ascii=False, indent=2))
