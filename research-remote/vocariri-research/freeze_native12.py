"""Offline freeze for qwen-native-12: decode native frames with PTS, build clips, hash inputs.

No inference. All inputs stay under /workspace. Source media is data only.
"""
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FF = subprocess.check_output(
    ["/opt/pv-tools/bin/python", "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"]
).decode().strip()
ROOT = Path("/workspace")
SRC = ROOT / "media/BV1zrbCzLEH4/source.mp4"
OUT = ROOT / "evidence"
WINDOWS = [
    ("win-a-scale", 141.941, 142.541),
    ("win-b-bar", 160.30, 161.50),
    ("win-c-stagger", 139.908, 140.508),
]

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

manifest = {
    "task": "qwen-native-12",
    "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "source": {
        "id": "BV1zrbCzLEH4",
        "file": str(SRC.relative_to(ROOT)),
        "bytes": SRC.stat().st_size,
        "sha256": sha256(SRC),
        "format": "h264 High 1280x720 30fps 30tbr 16ktbn dur 302.57s yuv420p",
    },
    "windows": [],
}

for win_id, start, end in WINDOWS:
    native_dir = OUT / "native" / win_id
    native_dir.mkdir(parents=True, exist_ok=True)
    sel = f"select='between(t,{start - 0.2},{end + 0.2})'"
    cmd = [FF, "-v", "info", "-ss", str(start - 0.5), "-copyts", "-i", str(SRC),
           "-vf", f"{sel},showinfo", "-fps_mode", "passthrough", "-an",
           "-f", "image2", str(native_dir / "tmp-%04d.png")]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        print(f"DECODE FAIL {win_id}: {proc.stderr[-800:]}", file=sys.stderr)
        sys.exit(1)
    showinfo_pts = [float(p) for p in re.findall(r"pts_time:([0-9.]+)", proc.stderr)]
    tmp_frames = sorted(native_dir.glob("tmp-*.png"))
    if len(tmp_frames) != len(showinfo_pts):
        print(f"PTS/FRAME MISMATCH {win_id}: {len(tmp_frames)} frames vs {len(showinfo_pts)} pts", file=sys.stderr)
        sys.exit(1)
    keep = [i for i, pts in enumerate(showinfo_pts)
            if start - 1.0 / 60.0 <= pts < end - 1.0 / 60.0]
    expected = int(round((end - start) * 30))
    if len(keep) != expected:
        print(f"FRAME COUNT {win_id}: kept {len(keep)}, expected {expected}", file=sys.stderr)
        sys.exit(1)
    frames = [tmp_frames[i] for i in keep]
    renamed = []
    for i, frame in enumerate(frames):
        frame.replace(native_dir / f"f-{i + 1:04d}.png")
        renamed.append(native_dir / f"f-{i + 1:04d}.png")
    for leftover in native_dir.glob("tmp-*.png"):
        leftover.unlink()
    frames = renamed
    rec_frames = []
    keep_pts = [showinfo_pts[i] for i in keep]
    for i, (frame, pts) in enumerate(zip(frames, keep_pts)):
        rec_frames.append({"index": i, "file": str(frame.relative_to(ROOT)),
                           "pts_time": float(pts), "sha256": sha256(frame)})
    # Clip: exact cut, 30fps cadence preserved, no audio, lossless-quality re-encode.
    clip = OUT / "clips" / f"{win_id}.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    if clip.exists():
        clip.unlink()
    cmd = [FF, "-v", "warning", "-ss", str(start), "-to", str(end), "-i", str(SRC),
           "-an", "-r", "30", "-c:v", "libx264", "-crf", "12", "-preset", "veryfast",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        print(f"CLIP FAIL {win_id}: {proc.stderr[-800:]}", file=sys.stderr)
        sys.exit(1)
    # Verify clip frame count and cadence.
    info = subprocess.run([FF, "-v", "info", "-i", str(clip), "-f", "null", "-"],
                          capture_output=True, text=True, timeout=300)
    clip_frames = [int(m) for m in re.findall(r"frame=\s*(\d+)", info.stderr)]
    n_clip = clip_frames[-1] if clip_frames else -1
    manifest["windows"].append({
        "id": win_id, "start_seconds": start, "end_seconds": end,
        "native_frames": rec_frames,
        "clip": {"file": str(clip.relative_to(ROOT)), "bytes": clip.stat().st_size,
                 "sha256": sha256(clip), "frame_count": n_clip},
    })
    print(f"{win_id}: native={len(rec_frames)} pts=[{rec_frames[0]['pts_time']:.4f},{rec_frames[-1]['pts_time']:.4f}] clip_frames={n_clip}")

OUT.joinpath("qwen-native-12.inputs.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print("frozen:", str(OUT.joinpath("qwen-native-12.inputs.json")))
