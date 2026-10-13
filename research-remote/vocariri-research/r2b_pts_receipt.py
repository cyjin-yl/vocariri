"""Qwen R2b: corrected offline source-to-clip native PTS receipts (single targeted attempt).

Reads frozen R1 inputs + the existing r2 preflight (never recreates it).
Time base from showinfo 'config in time_base:' line, cross-checked with stream '16k tbn'
and every integer pts / pts_time pair. New versioned outputs only (r2b names), exclusive
creation. No inference. No shell with media paths.
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
PREFLIGHT = EVID / "qwen-native-12-r2-preflight.json"
OUT_PREFIX = "qwen-native-12-r2b"
ERRORS = []

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

def fail(msg):
    ERRORS.append(msg)
    print(f"ERROR: {msg}", file=sys.stderr)

version = run([FF, "-version"]).stdout.splitlines()[0]

# ---------- preflight: read existing, never recreate ----------
inputs = json.loads(INPUTS.read_text(encoding="utf-8"))
preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
if preflight.get("failures"):
    fail(f"existing preflight reports failures: {preflight['failures']}")
src_sha = sha256(SRC)
src_size = SRC.stat().st_size
if src_sha != inputs["source"]["sha256"] or src_size != inputs["source"]["bytes"]:
    fail("source hash/size no longer matches R1 inputs")

# ---------- showinfo over the whole source ----------
cmd = [FF, "-nostdin", "-hide_banner", "-i", str(SRC), "-vf", "showinfo", "-an", "-f", "null", "-"]
p = run(cmd)
if p.returncode != 0:
    fail(f"showinfo failed rc={p.returncode}: {p.stderr[-400:]}")
stderr = p.stderr

cfg_in = re.findall(r"config in time_base: (\d+)/(\d+)", stderr)
cfg_out = re.findall(r"config out time_base: (\d+)/(\d+)", stderr)
tbn_m = re.search(r"([\d.k]+) tbn", stderr)
stream_line = next((ln.strip() for ln in stderr.splitlines() if "Stream #0:0" in ln), "")
if len(cfg_in) != 1:
    fail(f"expected exactly 1 'config in time_base' line, found {len(cfg_in)}")
if not tbn_m:
    fail("stream 'tbn' not found")
tb_num, tb_den = (int(x) for x in cfg_in[0]) if cfg_in else (0, 1)
tbn_val = int(float(tbn_m.group(1).rstrip("k")) * (1000 if tbn_m.group(1).endswith("k") else 1)) if tbn_m else 0
if tb_den != tbn_val:
    fail(f"time base {tb_num}/{tb_den} conflicts with stream {tbn_m.group(1) if tbn_m else '?'} tbn")

showinfo_lines = [ln for ln in stderr.splitlines() if "pts_time:" in ln]
frames = []
for ln in showinfo_lines:
    m = re.search(r"n:\s*(\d+) pts:\s*(\d+) pts_time:([0-9.]+)", ln)
    if not m:
        fail(f"unparsed showinfo line: {ln[:200]}")
        break
    n, pts, pts_time = int(m.group(1)), int(m.group(2)), float(m.group(3))
    if tb_den and abs(pts / tb_den - pts_time) > 0.002:
        fail(f"pts/time_base inconsistent n={n} pts={pts} pts_time={pts_time}")
        break
    frames.append({"n": n, "pts": pts, "pts_time": pts_time})
if not ERRORS:
    expected_n = len(showinfo_lines)
    if [f["n"] for f in frames] != list(range(expected_n)):
        fail(f"nonconsecutive frame indices: got {len(frames)} lines, first/last n={frames[0]['n'] if frames else '-'}/{frames[-1]['n'] if frames else '-'}")
    if len({f["pts"] for f in frames}) != len(frames):
        fail("duplicate integer pts detected")
print(f"frames={len(frames)} time_base={tb_num}/{tb_den} tbn={tbn_m.group(1) if tbn_m else '?'}")

# ---------- mapping R1 windows to native integer PTS ----------
mapping = {}
bounded = []
if not ERRORS:
    bounded = [stream_line,
               next(ln.strip() for ln in stderr.splitlines() if "config in time_base" in ln),
               next(ln.strip() for ln in stderr.splitlines() if "config out time_base" in ln),
               showinfo_lines[0].strip()]
for w in inputs["windows"]:
    wid = w["id"]
    win_frames, blocked = [], None
    for fr in w["native_frames"]:
        cands = [f for f in frames if abs(f["pts_time"] - fr["pts_time"]) < 1.0 / 60.0]
        if len(cands) != 1:
            blocked = f"ambiguous/missing native match for pts_time {fr['pts_time']}: {len(cands)} candidates"
            break
        win_frames.append(cands[0])
    if blocked:
        mapping[wid] = {"state": "blocked", "reason": blocked}
        continue
    idxs = [f["n"] for f in win_frames]
    if idxs != list(range(idxs[0], idxs[0] + len(idxs))):
        mapping[wid] = {"state": "blocked", "reason": f"mapped source indices nonconsecutive: {idxs[:3]}..{idxs[-3:]}"}
        continue
    if len(win_frames) != len(w["native_frames"]):
        mapping[wid] = {"state": "blocked", "reason": "count mismatch"}
        continue
    mapping[wid] = {"state": "mapped", "frames": win_frames}
    bounded.extend(l.strip() for l in showinfo_lines[idxs[0] - 1: idxs[-1] + 2])
print("mapping:", {k: v["state"] for k, v in mapping.items()})

# ---------- independent decode + quantitative comparison ----------
from PIL import Image, ImageDraw

comparison = {"task": OUT_PREFIX, "at": now(), "decoder": version,
              "source": {"file": str(SRC.relative_to(ROOT)), "sha256": src_sha, "bytes": src_size},
              "source_time_base": f"{tb_num}/{tb_den}",
              "stream_line": stream_line,
              "showinfo_command": [str(c) for c in cmd],
              "clip_provenance": "R1 re-encode: libx264 crf 12 preset veryfast, 30fps, yuv420p, no audio (lossy; pixel identity NOT expected, quantitative similarity used)",
              "windows": []}

def decode_window_frames(wid, start, end, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.png"):
        f.unlink()
    sel = f"select='between(t,{start - 0.2},{end + 0.2})'"
    c = [FF, "-nostdin", "-hide_banner", "-v", "info", "-ss", str(start - 0.5), "-copyts", "-i", str(SRC),
         "-vf", f"{sel},showinfo", "-fps_mode", "passthrough", "-an",
         "-f", "image2", str(outdir / "s-%04d.png")]
    pr = run(c)
    if pr.returncode != 0:
        raise RuntimeError(f"source decode failed {wid}: {pr.stderr[-400:]}")
    pts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", pr.stderr)]
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
    return renamed, [str(x) for x in c]

def decode_clip_frames(wid, clip, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.png"):
        f.unlink()
    c = [FF, "-nostdin", "-hide_banner", "-v", "info", "-i", str(clip),
         "-f", "image2", str(outdir / "c-%04d.png")]
    pr = run(c)
    if pr.returncode != 0:
        raise RuntimeError(f"clip decode failed {wid}: {pr.stderr[-400:]}")
    return sorted(outdir.glob("c-*.png")), [str(x) for x in c]

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
for w in inputs["windows"]:
    wid = w["id"]
    start, end = w["start_seconds"], w["end_seconds"]
    clip = ROOT / w["clip"]["file"]
    sdir, cdir = ROOT / f"r2btmp/{wid}/src", ROOT / f"r2btmp/{wid}/clip"
    if mapping[wid]["state"] != "mapped":
        comparison["windows"].append({"id": wid, "state": "blocked", "reason": mapping[wid]["reason"]})
        continue
    try:
        src_frames, s_cmd = decode_window_frames(wid, start, end, sdir)
        clip_frames, c_cmd = decode_clip_frames(wid, clip, cdir)
    except RuntimeError as e:
        mapping[wid] = {"state": "blocked", "reason": str(e)}
        comparison["windows"].append({"id": wid, "state": "blocked", "reason": str(e)})
        continue
    n_exp = len(w["native_frames"])
    counts_ok = len(src_frames) == len(clip_frames) == n_exp
    if not counts_ok:
        fail(f"{wid} frame count mismatch: source={len(src_frames)} clip={len(clip_frames)} expected={n_exp}")
    baseline_mads = []
    if counts_ok:
        for i in range(len(src_frames) - 1):
            r = mad_pair(src_frames[i][0], src_frames[i + 1][0])
            if r:
                baseline_mads.append(r["mad"])
    pairs, aligned = [], counts_ok
    for i in range(min(len(src_frames), len(clip_frames))):
        r = mad_pair(src_frames[i][0], clip_frames[i])
        if r is None:
            aligned = False
            break
        pairs.append(r)
        if baseline_mads and r["mad"] > max(baseline_mads) * 3:
            aligned = False
    idxs = sorted(set([0, len(src_frames) // 2, len(src_frames) - 1])) if src_frames else []
    W, H = 320, 180
    sheet = Image.new("RGB", (W * 2, H * len(idxs) + 16 * len(idxs) or 32), "black")
    dr = ImageDraw.Draw(sheet)
    for j, i in enumerate(idxs):
        sheet.paste(Image.open(src_frames[i][0]).resize((W, H)), (0, j * (H + 16)))
        sheet.paste(Image.open(clip_frames[i]).resize((W, H)), (W, j * (H + 16)))
        dr.text((2, j * (H + 16) + 1), f"src {src_frames[i][1]:.3f} | clip {i + 1}", fill="yellow")
    spot[wid] = str(ROOT / f"r2btmp/{wid}/spot.jpg")
    sheet.save(spot[wid], quality=88)
    state = "verified" if counts_ok and aligned and not ERRORS else "partial"
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
          "mad range", f"{min(x['mad'] for x in pairs):.3f}-{max(x['mad'] for x in pairs):.3f}" if pairs else "n/a")

# ---------- receipts (mapped + verified windows only) ----------
for w in inputs["windows"]:
    wid = w["id"]
    comp_state = next(cw["state"] for cw in comparison["windows"] if cw["id"] == wid)
    if mapping[wid]["state"] == "mapped" and comp_state == "verified":
        receipt = {
            "version": 1,
            "window_id": wid,
            "source_id": "BV1zrbCzLEH4",
            "source_sha256": src_sha,
            "source_time_base": f"{tb_num}/{tb_den}",
            "source_pts": [f["pts"] for f in mapping[wid]["frames"]],
            "frame_count": len(mapping[wid]["frames"]),
            "clip_sha256": sha256(ROOT / w["clip"]["file"]),
            "clip_bytes": (ROOT / w["clip"]["file"]).stat().st_size,
            "decoder": version,
            "created_at": now(),
            "note": "source_pts in decoded clip frame order; integer PTS in source time base; mapping by unique pts_time within 1 frame step",
        }
        exclusive_write(EVID / "native" / f"{wid}-pts-r2b.json", json.dumps(receipt, indent=2))
        print("receipt:", wid)

comparison["at"] = now()
comparison["decoder_evidence_bounded"] = bounded
exclusive_write(EVID / f"{OUT_PREFIX}-comparison.json", json.dumps(comparison, indent=2))
print("comparison written")
print("SPOT:", json.dumps(spot, indent=1))
print("ERRORS:", ERRORS)
