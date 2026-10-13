Synthetic image input returns an unrelated scene on a direct 1Cat-vLLM endpoint. This report describes a reproducible deployment symptom; I have not isolated the cause between the checkpoint, preprocessing, model runner or inference kernels.

Environment:
- 1cat-vllm 1.5.0 prebuilt cp312 Linux x86_64 wheel.
- 2 x NVIDIA V100 32 GB, tensor parallel size 2, dtype half.
- Model: ukisai/Swift-Qwen3.8-27B-NVFP4; architecture Qwen3_5ForConditionalGeneration, with vision weights present.
- VLLM_USE_V2_MODEL_RUNNER=1, VLLM_SM70_QUANT_BACKEND=turbomind.
- Language attention backend FLASH_ATTN_V100; startup reports TORCH_SDPA for MMEncoderAttention.

Relevant serving arguments (the model path and bind/auth configuration are deployment-specific):
```text
--dtype half --tensor-parallel-size 2
--attention-backend FLASH_ATTN_V100
--kv-cache-dtype fp8_e5m2 --max-model-len 262144
--gpu-memory-utilization 0.92
--max-num-batched-tokens 4096 --max-num-seqs 4
--enable-chunked-prefill --enable-prefix-caching --mamba-cache-mode align
--speculative-config '{"method":"mtp","num_speculative_tokens":4,"attention_backend":"FLASH_ATTN_V100"}'
--block-size 2048 --mamba-block-size 8192
--limit-mm-per-prompt '{"image":{"count":10,"width":512,"height":512},"video":{"count":1,"num_frames":8,"width":512,"height":512}}'
--media-io-kwargs '{"video":{"num_frames":8}}'
--mm-processor-kwargs '{"size":{"shortest_edge":4096,"longest_edge":262144}}'
--mm-processor-cache-gb 0.25
--reasoning-parser qwen3 --seed 0
```

Reproduction: install Pillow, save the following script, and run it against the engine directly. The image is generated locally: white background, red square on the left, blue circle on the right, black PV731 beneath. The prompt does not reveal the expected contents. No private or copyrighted media is required.

```python
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

```

Observed: HTTP 200, prompt_tokens=218, completion_tokens=200, finish_reason=length. The answer starts by describing a "scalloped border" and "silver or light gray" decorative elements, not the supplied shapes. Other image/video probes also produced unrelated scenes. A cache_salt was supplied; this is not proof that every multimodal cache was bypassed.

Localization checks:
- The same failure occurs directly at the engine, without NewAPI or another proxy.
- PNG input also fails, so a video-container problem alone cannot explain it.
- For a separate 8-second H.264 test clip, the installed VideoMediaIO loader returned the correct eight RGB frames; those decoded frames were visually checked.
- Several on-disk vision tensors have nonzero, finite-looking value ranges; this is not a full checkpoint-integrity or runtime-embedding validation.
- No no-MTP / V1-runner / eager-mode A/B has been performed: the shared service is busy and has not been restarted for this investigation.

Related searches: #53 documents vision support, #334 discusses enabling multimodality, and #634 references a different model's multimodal support. I did not find this exact wrong-image-content symptom. #656 concerns probabilistic draft sampling; the synthetic request here uses temperature=0 and the deployment does not explicitly select probabilistic draft sampling.

Is there a known compatibility limitation for this checkpoint + TP2 + V2/MTP configuration, or a recommended offline diagnostic for verifying encoder outputs and their insertion into the target model? I can provide further synthetic controls without sharing production inputs. This report and reproduction were prepared with AI assistance; the reported engine response and decoded-frame checks were performed, not inferred from HTTP success.
