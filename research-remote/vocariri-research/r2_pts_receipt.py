"""Qwen R2: offline source-to-clip native PTS receipts for the three frozen R1 windows.

No inference, no shell invocations with media paths (subprocess argument lists only).
Exclusive creation for all new artifacts; R1 files are read-only inputs.
"""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

FF = "/opt/pv-tools/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
ROOT = Path("/workspace")
EVID = ROOT / "evidence"
SRC = ROOT / "media/BV1zrbCzLEH4/source.mp4"
INPUTS = EVID / "qwen-native-12.inputs.json"

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

def exclusive_write(path, text):
    if path.exists():
        print(f"REFUSING OVERWRITE: {path}", file=sys.stderr)
        sys.exit(2)
    fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)

version = run([FF, "-version"]).stdout.splitlines()[0]

# ---------- Step 1: preflight ----------
inputs = json.loads(INPUTS.read_text(encoding="utf-8"))
preflight = {"task": "qwen-native-12-r2", "at": now(), "decoder": version,
             "checks": [], "failures": []}
src_sha = sha256(SRC)
src_size = SRC.stat().st_size
src_ok = (src_sha == inputs["source"]["sha256"] and src_size == inputs["source"]["bytes"])
preflight["checks"].append({"what": "source", "sha256_match": src_ok,
                            "bytes": [src_size, inputs["source"]["bytes"]]})
if not src_ok:
    preflight["failures"].append("source hash/size mismatch")

windows = []
for w in inputs["windows"]:
    wid = w["id"]
    rec = {"id": wid}
    nat_ok = True
    for fr in w["native_frames"]:
        if sha256(ROOT / fr["file"]) != fr["sha256"]:
            nat_ok = False
            preflight["failures"].append(f"{wid} native frame hash mismatch {fr['file']}")
    rec["native_frames_recorded"] = len(w["native_frames"])
    clip = ROOT / w["clip"]["file"]
    clip_ok = (sha256(clip) == w["clip"]["sha256"] and clip.stat().st_size == w["clip"]["bytes"])
    rec["clip_bytes"] = [clip.stat().st_size, w["clip"]["bytes"]]
    rec["clip_sha256_match"] = clip_ok
    if not clip_ok:
        preflight["failures"].append(f"{wid} clip hash/size mismatch")
    rec["native_frames_all_match"] = nat_ok
    windows.append((wid, w, rec))
    preflight["checks"].append({"what": f"window {wid}", **rec})

if preflight["failures"]:
    exclusive_write(EVID / "qwen-native-12-r2-preflight.json", json.dumps(preflight, indent=2))
    print("PREFLIGHT FAIL:", preflight["failures"], file=sys.stderr)
    sys.exit(1)
exclusive_write(EVID / "qwen-native-12-r2-preflight.json", json.dumps(preflight, indent=2))
print("preflight ok:", version)

# ---------- Step 2: native integer PTS for the whole source ----------
probe = run([FF, "-nostdin", "-hide_banner", "-i", str(SRC)])
tb_m = re.search(r"Time base: (\d+)/(\d+)", probe.stderr)
tbn_m = re.search(r"([\d.k]+) tbn", probe.stderr)
if not tb_m:
    print("NO STREAM TIME BASE:", probe.stderr[-400:], file=sys.stderr)
    sys.exit(1)
time_base = f"{tb_m.group(1)}/{tb_m.group(2)}"
tb_den = int(tb_m.group(2))
cmd = [FF, "-nostdin", "-hide_banner", "-i", str(SRC), "-vf", "showinfo", "-an", "-f", "null", "-"]
p = run(cmd)
if p.returncode != 0:
    print("SHOWINFO FAIL:", p.stderr[-800:], file=sys.stderr)
    sys.exit(1)
showinfo_lines = [ln for ln in p.stderr.splitlines() if "pts_time:" in ln]
frames = []
for ln in showinfo_lines:
    m = re.search(r"n:\s*(\d+) pts:\s*(\d+) pts_time:([0-9.]+)", ln)
    if not m:
        print("UNPARSED SHOWINFO LINE:", ln[:200], file=sys.stderr)
        sys.exit(1)
    n, pts, pts_time = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if abs(pts / tb_den - pts_time) > 0.002:
        print(f"PTS/TIMEBASE INCONSISTENT n={n} pts={pts} pts_time={pts_time}", file=sys.stderr)
        sys.exit(1)
    frames.append({"n": n, "pts": pts, "pts_time": pts_time})
print(f"source frames: {len(frames)} time_base: {time_base} tbn: {tbn_m.group(1) if tbn_m else 'unknown'}")

# window mapping + bounded decoder evidence
mapping = {}
bounded = [showinfo_lines[0]]
for wid, w, _rec in windows:
    win_frames = []
    for fr in w["native_frames"]:
        target = fr["pts_time"]
        cands = [f for f in frames if abs(f["pts_time"] - target) < 1.0 / 60.0]
        if len(cands) != 1:
            mapping[wid] = {"state": "blocked",
                            "reason": f"ambiguous/missing native mapping for pts_time {target}: {len(cands)} candidates"}
            break
        win_frames.append(cands[0])
    if wid not in mapping:
        mapping[wid] = {"state": "mapped", "frames": win_frames}
        i0, i1 = frames.index(win_frames[0]), frames.index(win_frames[-1])
        bounded.extend(showinfo_lines[max(0, i0 - 1): i1 + 2])
exclusive_write(EVID / "native" / "pts-showinfo-r2-bounded.txt", "\n".join(bounded) + "\n")
print("mapping states:", {k: v["state"] for k, v in mapping.items()})

# ---------- Step 3: independent decode + comparison ----------
from PIL import Image, ImageDraw

comparison = {"task": "qwen-native-12-r2", "at": now(), "decoder": version,
              "source": {"file": str(SRC.relative_to(ROOT)), "sha256": src_sha, "bytes": src_size},
              "source_time_base": time_base,
              "clip_provenance": "R1 re-encode: libx264 crf 12 preset veryfast, 30fps, yuv420p, no audio (lossy; pixel identity NOT expected)",
              "windows": []}

def decode_window_frames(wid, start, end, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.png"):
        f.unlink()
    sel = f"select='between(t,{start - 0.2},{end + 0.2})'"
    cmd = [FF, "-nostdin", "-hide_banner", "-v", "info", "-ss", str(start - 0.5), "-copyts", "-i", str(SRC),
           "-vf", f"{sel},showinfo", "-fps_mode", "passthrough", "-an",
           "-f", "image2", str(outdir / "s-%04d.png")]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"source decode failed {wid}: {p.stderr[-400:]}")
    pts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", p.stderr)]
    fs = sorted(outdir.glob("s-*.png"))
    if len(fs) != len(pts):
        raise RuntimeError(f"source decode pts/frame mismatch {wid}")
    half = 1.0 / 60.0
    kept = [(i, f) for i, f in enumerate(fs) if start - half <= pts[i] < end - half]
    renamed = []
    for j, (i, f) in enumerate(kept):
        f.replace(outdir / f"src-{j + 1:03d}.png")
        renamed.append((outdir / f"src-{j + 1:03d}.png", pts[i]))
    for f in outdir.glob("s-*.png"):
        f.unlink()
    return renamed, [str(c) for c in cmd]

def decode_clip_frames(wid, clip, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.png"):
        f.unlink()
    cmd = [FF, "-nostdin", "-hide_banner", "-v", "info", "-i", str(clip),
           "-f", "image2", str(outdir / "c-%04d.png")]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"clip decode failed {wid}: {p.stderr[-400:]}")
    fs = sorted(outdir.glob("c-*.png"))
    return fs, [str(c) for c in cmd]

def mad_pair(a, b):
    ia, ib = Image.open(a).convert("L"), Image.open(b).convert("L")
    if ia.size != ib.size:
        return None
    pa, pb = ia.tobytes(), ib.tobytes()
    n = len(pa)
    total = mx = over = 0
    for x, y in zip(pa, pb):
        d = abs(x - y)
        total += d
        if d > mx:
            mx = d
        if d > 8:
            over += 1
    return {"mad": total / n, "max_diff": mx, "pct_gt8": 100.0 * over / n}

spot = {}
for wid, w, _rec in windows:
    start, end = w["start_seconds"], w["end_seconds"]
    clip = ROOT / w["clip"]["file"]
    sdir = ROOT / f"r2tmp/{wid}/src"
    cdir = ROOT / f"r2tmp/{wid}/clip"
    try:
        src_frames, s_cmd = decode_window_frames(wid, start, end, sdir)
        clip_frames, c_cmd = decode_clip_frames(wid, clip, cdir)
    except RuntimeError as e:
        mapping[wid] = {"state": "blocked", "reason": str(e)}
        comparison["windows"].append({"id": wid, "state": "blocked", "reason": str(e)})
        continue
    n_exp = len(w["native_frames"])
    counts_ok = len(src_frames) == len(clip_frames) == n_exp
    baseline_mads = []
    if counts_ok:
        for i in range(len(src_frames) - 1):
            r = mad_pair(src_frames[i][0], src_frames[i + 1][0])
            if r:
                baseline_mads.append(r["mad"])
    pairs = []
    aligned = counts_ok
    for i in range(min(len(src_frames), len(clip_frames))):
        r = mad_pair(src_frames[i][0], clip_frames[i])
        pairs.append(r)
        if counts_ok and baseline_mads and r["mad"] > max(baseline_mads) * 3:
            aligned = False
    idxs = sorted(set([0, len(src_frames) // 2, len(src_frames) - 1]))
    W, H = 320, 180
    sheet = Image.new("RGB", (W * 2, H * len(idxs) + 16 * len(idxs)), "black")
    dr = ImageDraw.Draw(sheet)
    for j, i in enumerate(idxs):
        sheet.paste(Image.open(src_frames[i][0]).resize((W, H)), (0, j * (H + 16)))
        sheet.paste(Image.open(clip_frames[i]).resize((W, H)), (W, j * (H + 16)))
        dr.text((2, j * (H + 16) + 1), f"src {src_frames[i][1]:.3f} | clip {i + 1}", fill="yellow")
    spot[wid] = str(ROOT / f"r2tmp/{wid}/spot.jpg")
    sheet.save(spot[wid], quality=88)
    state = "verified" if counts_ok and aligned else "partial"
    comparison["windows"].append({
        "id": wid, "state": state,
        "frame_counts": {"source": len(src_frames), "clip": len(clip_frames), "expected": n_exp},
        "aligned": aligned,
        "pair_mad": [round(x["mad"], 4) for x in pairs],
        "pair_max_diff": [x["max_diff"] for x in pairs],
        "pair_pct_gt8": [round(x["pct_gt8"], 3) for x in pairs],
        "commands": {"source_decode": s_cmd, "clip_decode": c_cmd},
    })
    print(wid, state, "counts", len(src_frames), len(clip_frames),
          "mad range", f"{min(x['mad'] for x in pairs):.3f}-{max(x['mad'] for x in pairs):.3f}")

# ---------- Step 4: receipts (passing windows only) ----------
for wid, w, _rec in windows:
    st = mapping[wid]["state"]
    comp_state = next(cw["state"] for cw in comparison["windows"] if cw["id"] == wid)
    if st == "mapped" and comp_state == "verified":
        receipt = {
            "version": 1,
            "window_id": wid,
            "source_id": "BV1zrbCzLEH4",
            "source_sha256": src_sha,
            "source_time_base": time_base,
            "source_pts": [f["pts"] for f in mapping[wid]["frames"]],
            "frame_count": len(mapping[wid]["frames"]),
            "clip_sha256": sha256(ROOT / w["clip"]["file"]),
            "decoder": version,
            "created_at": now(),
            "note": "source_pts in decoded clip frame order; integer PTS in source time base",
        }
        exclusive_write(EVID / "native" / f"{wid}-pts-r2.json", json.dumps(receipt, indent=2))
        print("receipt:", wid)

comparison["at"] = now()
exclusive_write(EVID / "qwen-native-12-r2-comparison.json", json.dumps(comparison, indent=2))
print("comparison written")
print("SPOT:", json.dumps(spot, indent=1))
