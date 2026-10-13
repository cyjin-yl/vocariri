"""Qwen R3a: one native-cadence MP4 repair for win-a-scale, offline.

Selects the frozen 18 consecutive source frames by native index, resets only the PTS
origin (setpts=PTS-STARTPTS), preserves exact native PTS deltas via passthrough sync and
source-aligned encoder/container time bases. No fps filter, no output -r.
New versioned outputs only (r3a names), exclusive creation. No inference, no network.
"""
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

FF = "/opt/pv-tools/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
ROOT = Path("/workspace")
EVID = ROOT / "evidence"
SRC = ROOT / "media/BV1zrbCzLEH4/source.mp4"
OLD_CLIP = EVID / "clips/win-a-scale.mp4"
R2B_RECEIPT = EVID / "native/win-a-scale-pts-r2b.json"
NEW_CLIP = EVID / "native" / "win-a-scale-native-r3.mp4"
NEW_RECEIPT = EVID / "native" / "win-a-scale-pts-r3a.json"
COMPARISON = EVID / "qwen-native-12-r3a-comparison.json"
STATUS = EVID / "qwen-native-12-r3a.status.json"
WID = "win-a-scale"
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

# ---------- step 1: freeze hashes + independent native PTS ----------
src_sha = sha256(SRC)
old_clip_sha = sha256(OLD_CLIP)
r2b = json.loads(R2B_RECEIPT.read_text(encoding="utf-8"))
hashes = {
    "source": {"file": str(SRC.relative_to(ROOT)), "sha256": src_sha, "bytes": SRC.stat().st_size},
    "old_clip_r1": {"file": str(OLD_CLIP.relative_to(ROOT)), "sha256": old_clip_sha, "bytes": OLD_CLIP.stat().st_size},
    "old_receipt_r2b": {"file": str(R2B_RECEIPT.relative_to(ROOT)), "sha256": sha256(R2B_RECEIPT), "bytes": R2B_RECEIPT.stat().st_size},
}
if r2b.get("source_sha256") != src_sha:
    fail("r2b receipt source hash does not match source file")
if r2b.get("clip_sha256") != old_clip_sha:
    fail("r2b receipt clip hash does not match old clip file")

probe = run([FF, "-nostdin", "-hide_banner", "-i", str(SRC)])
stream_line = next(ln.strip() for ln in probe.stderr.splitlines() if "Stream #0:0" in ln)
pix_fmt = re.search(r", (\w+)\(", stream_line)
codec = re.search(r"Video: (\w+)", stream_line)
tb_m = re.search(r"Time base: (\d+)/(\d+)", probe.stderr)
tbn_m = re.search(r"([\d.k]+) tbn", probe.stderr)
source_meta = {"stream_line": stream_line,
               "codec": codec.group(1) if codec else "unknown",
               "pix_fmt": pix_fmt.group(1) if pix_fmt else "unknown",
               "tbn": tbn_m.group(1) if tbn_m else "unknown",
               "encoder_tags": [ln.strip() for ln in probe.stderr.splitlines()
                                if re.search(r"(major_brand|encoder|handler_name)", ln)][:6]}

cmd = [FF, "-nostdin", "-hide_banner", "-i", str(SRC), "-vf", "showinfo", "-an", "-f", "null", "-"]
p = run(cmd)
if p.returncode != 0:
    fail(f"source showinfo failed rc={p.returncode}")
cfg = re.findall(r"config in time_base: (\d+)/(\d+)", p.stderr)
if len(cfg) != 1:
    fail(f"expected one config-in time base, found {len(cfg)}")
tb_num, tb_den = (int(x) for x in cfg[0]) if cfg else (0, 1)
if tb_den != int(float(tbn_m.group(1).rstrip("k")) * (1000 if tbn_m.group(1).endswith("k") else 1)) if tbn_m else False:
    fail("showinfo time base conflicts with stream tbn")
lines = [ln for ln in p.stderr.splitlines() if "pts_time:" in ln]
frames = []
for ln in lines:
    m = re.search(r"n:\s*(\d+) pts:\s*(\d+) pts_time:([0-9.]+)", ln)
    if not m:
        fail(f"unparsed showinfo line: {ln[:200]}")
        break
    frames.append({"n": int(m.group(1)), "pts": int(m.group(2)), "pts_time": float(m.group(3))})
if [f["n"] for f in frames] != list(range(len(lines))) or len({f["pts"] for f in frames}) != len(frames):
    fail("nonconsecutive indices or duplicate integer pts in source")

r2b_pts = r2b.get("source_pts", [])
if len(r2b_pts) != 18:
    fail(f"r2b receipt has {len(r2b_pts)} pts, expected 18")
idx_by_pts = {f["pts"]: f for f in frames}
win = [idx_by_pts.get(pts) for pts in r2b_pts]
if any(f is None for f in win):
    fail("r2b pts not found in fresh source showinfo")
else:
    ns = [f["n"] for f in win]
    if ns != list(range(ns[0], ns[0] + 18)):
        fail(f"r2b frames not consecutive: {ns}")
    if [f["pts"] for f in win] != r2b_pts:
        fail("fresh source integer PTS differ from r2b receipt")
print(f"win-a native indices {ns[0]}..{ns[-1]}, exact source pts read from showinfo")

# ---------- step 2: build new native-cadence clip ----------
if NEW_CLIP.exists():
    fail("new clip path already exists; refusing to overwrite")
start_n, end_n = win[0]["n"], win[-1]["n"]
build_cmd = [FF, "-nostdin", "-hide_banner", "-i", str(SRC), "-map", "0:v:0",
             "-vf", f"select='between(n,{start_n},{end_n})',setpts=PTS-STARTPTS",
             "-fps_mode", "passthrough", "-enc_time_base", "filter",
             "-video_track_timescale", str(tb_den), "-an",
             "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(NEW_CLIP)]
bp = run(build_cmd)
if bp.returncode != 0:
    fail(f"clip build failed rc={bp.returncode}: {bp.stderr[-500:]}")
    NEW_CLIP.unlink(missing_ok=True)
new_clip_sha = sha256(NEW_CLIP) if NEW_CLIP.exists() else None
if not NEW_CLIP.exists():
    fail("new clip was not produced")
print("new clip bytes:", NEW_CLIP.stat().st_size if NEW_CLIP.exists() else None, "sha256:", (new_clip_sha or "")[:16])

# ---------- step 3: decode new clip independently ----------
from PIL import Image, ImageDraw

clip_probe = run([FF, "-nostdin", "-hide_banner", "-i", str(NEW_CLIP)])
clip_stream = next(ln.strip() for ln in clip_probe.stderr.splitlines() if "Stream #0:0" in ln)
clip_tb_m = re.search(r"Time base: (\d+)/(\d+)", clip_probe.stderr)
clip_tb = f"{clip_tb_m.group(1)}/{clip_tb_m.group(2)}" if clip_tb_m else "unknown"
dc = [FF, "-nostdin", "-hide_banner", "-v", "info", "-i", str(NEW_CLIP),
      "-vf", "showinfo", "-fps_mode", "passthrough", "-an",
      "-f", "image2", str(ROOT / f"r3atmp/{WID}/c-%04d.png")]
(ROOT / f"r3atmp/{WID}").mkdir(parents=True, exist_ok=True)
d = run(dc)
if d.returncode != 0:
    fail(f"new clip decode failed: {d.stderr[-400:]}")
clip_pts = [int(x) for x in re.findall(r"n:\s*\d+ pts:\s*(-?\d+) pts_time:", d.stderr)]
cfg_clip = re.findall(r"config in time_base: (\d+)/(\d+)", d.stderr)
clip_files = sorted((ROOT / f"r3atmp/{WID}").glob("c-*.png"))
if len(clip_pts) != 18 or len(clip_files) != 18:
    fail(f"new clip decoded {len(clip_pts)} pts / {len(clip_files)} frames, expected 18")
if len(cfg_clip) != 1:
    fail(f"new clip showinfo config-in count {len(cfg_clip)}")
clip_tb2 = f"{cfg_clip[0][0]}/{cfg_clip[0][1]}" if cfg_clip else "unknown"
if clip_tb2 != "unknown" and clip_tb != "unknown" and clip_tb2 != clip_tb:
    fail(f"clip stream tb {clip_tb} != filter config-in tb {clip_tb2}")
mono = all(b > a for a, b in zip(clip_pts, clip_pts[1:]))
if not mono:
    fail("new clip pts not strictly increasing")

src_pts = [f["pts"] for f in win]
src_deltas = [b - a for a, b in zip(src_pts, src_pts[1:])]
clip_deltas = [b - a for a, b in zip(clip_pts, clip_pts[1:])]
tb_src = Fraction(tb_num, tb_den)
tb_clip = Fraction(clip_tb2) if re.fullmatch(r"\d+/\d+", clip_tb2) else Fraction(0, 1)
delta_exact = all(sd * tb_src == cd * tb_clip for sd, cd in zip(src_deltas, clip_deltas))
drifts = []
for i in range(1, 18):
    src_e = (src_pts[i] - src_pts[0]) * tb_src
    clip_e = (clip_pts[i] - clip_pts[0]) * tb_clip
    drifts.append(abs(src_e - clip_e))
max_drift = max(drifts) if drifts else None
bound = tb_src + tb_clip
min_gap = min(Fraction(g) * tb_src for g in src_deltas)
client_bounds_ok = all(dr <= bound and 2 * dr < min_gap for dr in drifts)
if not delta_exact:
    fail("clip deltas differ from source rational deltas")
print(f"clip tb {clip_tb}; deltas exact: {delta_exact}; max cumulative drift {max_drift} "
      f"(bound {bound}, half-min-gap {min_gap / 2}); client bounds ok: {client_bounds_ok}")

# ---------- step 4: image correspondence ----------
sdir = ROOT / f"r3atmp/{WID}/src"
sdir.mkdir(exist_ok=True)
for f in sdir.glob("*.png"):
    f.unlink()
sel_cmd = [FF, "-nostdin", "-hide_banner", "-v", "info", "-ss", str(win[0]["pts_time"] - 0.5),
           "-copyts", "-i", str(SRC),
           "-vf", f"select='between(n,{start_n},{end_n})',showinfo", "-fps_mode", "passthrough",
           "-an", "-f", "image2", str(sdir / "s-%04d.png")]
sp = run(sel_cmd)
if sp.returncode != 0:
    fail(f"source window decode failed: {sp.stderr[-400:]}")
src_files = sorted(sdir.glob("s-*.png"))
if len(src_files) != 18:
    fail(f"source window decoded {len(src_files)} frames, expected 18")

def mad_pair(a, b):
    ia, ib = Image.open(a).convert("L"), Image.open(b).convert("L")
    pa, pb = ia.tobytes(), ib.tobytes()
    n = len(pa)
    total = mx = over = 0
    for x, y in zip(pa, pb):
        dd = abs(x - y)
        total += dd
        if dd > mx:
            mx = dd
        if dd > 8:
            over += 1
    return {"mad": total / n, "max_diff": mx, "pct_gt8": 100.0 * over / n}

mads = [mad_pair(a, b) for a, b in zip(src_files, clip_files)]
idxs = [0, 9, 17]
W, H = 320, 180
sheet = Image.new("RGB", (W * 2, H * len(idxs) + 16 * len(idxs)), "black")
dr = ImageDraw.Draw(sheet)
for j, i in enumerate(idxs):
    sheet.paste(Image.open(src_files[i]).resize((W, H)), (0, j * (H + 16)))
    sheet.paste(Image.open(clip_files[i]).resize((W, H)), (W, j * (H + 16)))
    dr.text((2, j * (H + 16) + 1), f"src n={win[i]['n']} | clip {i + 1}", fill="yellow")
spot = ROOT / f"r3atmp/{WID}/spot.jpg"
sheet.save(spot, quality=88)
print("mad range:", f"{min(x['mad'] for x in mads):.3f}-{max(x['mad'] for x in mads):.3f}")

# ---------- step 5: receipt + checked-client validation ----------
receipt = {
    "version": 1,
    "window_id": WID,
    "source_id": "BV1zrbCzLEH4",
    "source_sha256": src_sha,
    "source_time_base": f"{tb_num}/{tb_den}",
    "source_pts": src_pts,
    "frame_count": 18,
    "clip_sha256": new_clip_sha,
    "clip_bytes": NEW_CLIP.stat().st_size,
    "decoder": version,
    "created_at": now(),
    "note": ("source_pts = exact integer source PTS (source time base) in decoded clip order; "
             "new clip preserves each native PTS delta exactly (passthrough, enc_time_base filter, "
             "video_track_timescale=16000); old R1 clip on 1/15360 grid is not receipt-compatible"),
}
exclusive_write(NEW_RECEIPT, json.dumps(receipt, indent=2))

client_result, client_err = None, None
try:
    sys.path.insert(0, str(ROOT / "checked-client-20260927/remote"))
    import video_request_checked as vrc
    probe_result = vrc.probe_video(NEW_CLIP)
    client_result = {"probe": probe_result}
    client_result["validate"] = vrc.validate_native_receipt(NEW_RECEIPT, ROOT, new_clip_sha, probe_result)
except Exception as e:
    client_err = f"{type(e).__name__}: {e}"
print("client:", json.dumps(client_result) if client_result else f"FAIL {client_err}")

comparison = {
    "task": "qwen-native-12-r3a", "at": now(), "decoder": version,
    "hashes_frozen": hashes,
    "source_meta": source_meta,
    "win": {"index_range": [start_n, end_n], "source_pts": src_pts,
            "source_deltas_ticks": src_deltas,
            "delta_values_seconds": [str(Fraction(g) * tb_src) for g in src_deltas]},
    "new_clip": {"file": str(NEW_CLIP.relative_to(ROOT)), "sha256": new_clip_sha,
                 "bytes": NEW_CLIP.stat().st_size if NEW_CLIP.exists() else None,
                 "stream_line": clip_stream, "stream_time_base": clip_tb,
                 "showinfo_config_in_time_base": clip_tb2},
    "clip_decode": {"pts_ticks": clip_pts, "deltas_ticks": clip_deltas,
                    "strictly_increasing": mono,
                    "deltas_exact_rational_match": delta_exact,
                    "cumulative_drifts": [str(x) for x in drifts],
                    "max_drift": str(max_drift),
                    "client_bounds": {"drift_bound": str(bound), "half_min_source_gap": str(min_gap / 2),
                                      "all_within": client_bounds_ok}},
    "image_correspondence": {"per_pair_mad": [round(x["mad"], 4) for x in mads],
                             "per_pair_max_diff": [x["max_diff"] for x in mads],
                             "per_pair_pct_gt8": [round(x["pct_gt8"], 3) for x in mads],
                             "spot_sheet": str(spot.relative_to(ROOT)),
                             "note": "CRF12 lossy re-encode; quantitative similarity, not pixel identity"},
    "build_command": [str(c) for c in build_cmd],
    "source_window_decode_command": [str(c) for c in sel_cmd],
    "clip_decode_command": [str(c) for c in dc],
    "checked_client": {"result": client_result, "error": client_err,
                       "invocation": "vrc.probe_video(new_clip); vrc.validate_native_receipt(receipt, /workspace, clip_sha, probe)"},
    "errors": ERRORS,
}
exclusive_write(COMPARISON, json.dumps(comparison, indent=2))
print("comparison written; errors:", ERRORS)
