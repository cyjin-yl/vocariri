import subprocess, hashlib, json, os, re

FF = "/opt/pv-tools/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SRC = {
 "NICO-sm45786816": ("discovery-cross-18/sources/NICO-sm45786816/source.mp4", 300, 400, 30),
 "NICO-sm45669453": ("discovery-cross-18/sources/NICO-sm45669453/source.mp4", 85, 136, 24),
 "NICO-sm46320139": ("discovery-cross-18/sources/NICO-sm46320139/source.mp4", 250, 300, 30),
}
FBYTES = 854*480*3//2
assert FBYTES == 614880

for sid, (src, a, b, fps) in SRC.items():
    outdir = f"evidence/batch18-qwen-r1/{sid}"
    # showinfo: n is the post-select counter; pts is the true source PTS (1/90000)
    log = subprocess.run([FF, "-nostdin", "-hide_banner", "-i", src,
        "-vf", f"select='between(n,{a},{b})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    with open(f"{outdir}/showinfo-window.log", "w") as f:
        f.write(log)
    pts = [int(p) for p in re.findall(r"\] n:\s*\d+ pts:\s*(\d+)", log)]
    nframes = b - a + 1
    assert len(pts) == nframes, (sid, len(pts), nframes)
    subprocess.run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", src,
        "-vf", f"select='between(n,{a},{b})'", "-vsync", "0",
        f"{outdir}/native-n%04d.png"], check=True)
    pngs = sorted(p for p in os.listdir(outdir) if p.startswith("native-n") and p.endswith(".png"))
    raw = subprocess.run([FF, "-nostdin", "-hide_banner", "-loglevel", "error", "-i", src,
        "-vf", f"select='between(n,{a},{b})'", "-vsync", "0",
        "-f", "rawvideo", "-pix_fmt", "yuv420p", "pipe:1"],
        capture_output=True, check=True).stdout
    assert len(raw) == nframes*FBYTES, (sid, len(raw), nframes*FBYTES)
    hashes = {}
    for i in range(nframes):
        sn = a + i
        entry = {
            "source_n": sn,
            "md5": hashlib.md5(raw[i*FBYTES:(i+1)*FBYTES]).hexdigest(),
            "pts_90k": pts[i],
            "pts_time": pts[i]/90000.0,
            "png": f"{outdir}/native-n{i+1:04d}.png",
        }
        hashes[str(sn)] = entry
    assert len(pngs) == nframes, (sid, len(pngs), nframes)
    deltas = [pts[i+1]-pts[i] for i in range(nframes-1)]
    rec = {
        "id": sid, "window_n": [a, b], "count": nframes, "timebase": "1/90000",
        "fps": fps, "pts_90k_first": pts[0], "pts_90k_last": pts[-1],
        "pts_deltas_unique": sorted(set(deltas)), "frame_bytes": FBYTES,
        "dimension": [854, 480], "pix_fmt": "yuv420p", "frames": hashes,
        "png_count": len(pngs),
        "note": "showinfo n is the post-select counter; pts is the true source PTS in 1/90000; raw decode required -vsync 0 (default fps_mode duplicated frames: 401 vs 101 for w1)",
    }
    with open(f"{outdir}/window.json", "w") as f:
        json.dump(rec, f, indent=1)
    print(sid, "frames:", nframes, "deltas:", sorted(set(deltas)),
          "first_pts:", pts[0], "last_pts:", pts[-1],
          "raw_ok:", len(raw) == nframes*FBYTES)
