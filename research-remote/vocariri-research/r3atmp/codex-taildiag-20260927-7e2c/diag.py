"""Read-only-source, offline MP4 tail-frame diagnostics; outputs stay in this directory."""
import hashlib
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path("/workspace")
DIAG = ROOT / "r3atmp/codex-taildiag-20260927-7e2c"
FF = "/opt/pv-tools/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SOURCE = ROOT / "media/BV1zrbCzLEH4/source.mp4"
R3A = ROOT / "evidence/native/win-a-scale-native-r3.mp4"
SRC_HASH = "9ab2c3cf22f64965ba76642c7fbb8d5fc8e760e51349d31692305a2f43ee84d7"
R3A_HASH = "2c350b3886619f0492119abb474a98e078ae6181e6597ffedaf270ea256fdc59"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save_json(name, data):
    with (DIAG / name).open("x", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write("\n")

def run(name, args, timeout=120):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    with (DIAG / (name + ".stdout")).open("x", encoding="utf-8") as out:
        out.write(result.stdout)
    with (DIAG / (name + ".stderr")).open("x", encoding="utf-8") as out:
        out.write(result.stderr)
    return {"argv": [str(x) for x in args], "returncode": result.returncode,
            "stdout_sha256": sha(DIAG / (name + ".stdout")),
            "stderr_sha256": sha(DIAG / (name + ".stderr"))}, result

def showinfo(log):
    tb = re.findall(r"config in time_base:\s*(\d+/\d+)", log)
    rows = [(int(n), int(pts)) for n, pts in re.findall(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:", log)]
    return (tb[0] if len(tb) == 1 else None), rows

def source_check():
    assert sha(SOURCE) == SRC_HASH and sha(R3A) == R3A_HASH
    command = [FF, "-nostdin", "-hide_banner", "-loglevel", "info", "-i", str(SOURCE),
               "-map", "0:v:0", "-vf", "select=between(n\\,4258\\,4275),showinfo",
               "-fps_mode", "passthrough", "-an", "-sn", "-dn", "-f", "null", "-"]
    trace, result = run("source-scan", command)
    tb, rows = showinfo(result.stderr)
    expected = [2271056,2271584,2272128,2272656,2273184,2273728,2274256,
                2274800,2275328,2275856,2276400,2276928,2277456,2278000,
                2278528,2279056,2279600,2280128]
    assert result.returncode == 0 and tb == "1/16000" and [p for _,p in rows] == expected
    data = {"ffmpeg_version": subprocess.run([FF,"-version"],capture_output=True,text=True,check=True).stdout.splitlines()[0],
            "source_sha256": sha(SOURCE), "r3a_sha256": sha(R3A),
            "source_pts": expected, "source_time_base": tb, "source_scan": trace}
    save_json("source-check.json", data)
    return expected

def evaluate(label, path, source_pts, traces):
    ffprobe_cmd = [FF, "-nostdin", "-hide_banner", "-loglevel", "info", "-copyts",
                   "-noautorotate", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
                   "-vf", "showinfo", "-fps_mode", "passthrough", "-progress", "pipe:1",
                   "-nostats", "-f", "null", "-"]
    trace, decoded = run(label+"-decode", ffprobe_cmd)
    traces.append(trace)
    tb, rows = showinfo(decoded.stderr)
    pts = [p for _,p in rows]
    expected_relative = [p-source_pts[0] for p in source_pts]
    strict = decoded.returncode == 0 and len(pts)==18 and tb=="1/16000" and pts==expected_relative
    candidate = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha(path),
                 "decoded_count": len(pts), "decoded_time_base": tb,
                 "decoded_pts": pts, "expected_relative_pts": expected_relative,
                 "strict_native_pts_equal": strict, "decode_trace": trace}
    sys.path.insert(0, str(ROOT / "checked-client-20260927/remote"))
    import video_request_checked as vrc
    try:
        probe = vrc.probe_video(path)
        candidate["client_probe"] = {"ok": True, "decoded_frames": probe["decoded_frames"],
                                     "time_base": probe["time_base"], "pts": probe["pts"],
                                     "duration_seconds": probe["duration_seconds"]}
        receipt = DIAG / (label + "-test-receipt.json")
        with receipt.open("x", encoding="utf-8") as out:
            json.dump({"version":1,"clip_sha256":candidate["sha256"],"source_sha256":SRC_HASH,
                       "source_time_base":"1/16000","source_pts":source_pts}, out)
            out.write("\n")
        try:
            checked = vrc.validate_native_receipt(receipt, ROOT, candidate["sha256"], probe)
            candidate["client_receipt"] = {"ok":True, "receipt_sha256":checked["receipt_sha256"]}
        except vrc.ClientError as error:
            candidate["client_receipt"] = {"ok":False, "category":error.category}
    except vrc.ClientError as error:
        candidate["client_probe"] = {"ok":False, "category":error.category}
        candidate["client_receipt"] = {"ok":False, "reason":"probe_failed"}
    return candidate

def method_remux(srcpts):
    traces=[]
    mkv=DIAG/"remux-input.mkv"
    clip=DIAG/"remux.mp4"
    encode=[FF,"-nostdin","-hide_banner","-n","-i",str(SOURCE),"-map","0:v:0",
            "-vf","select=between(n\\,4258\\,4275),setpts=PTS-STARTPTS",
            "-fps_mode","passthrough","-enc_time_base","filter","-an",
            "-c:v","libx264","-crf","12","-pix_fmt","yuv420p",str(mkv)]
    trace, res=run("remux-mkv-encode",encode); traces.append(trace)
    if res.returncode:
        return {"method":"mkv_to_mp4_stream_copy","build_traces":traces,"error":"mkv_encode_failed"}
    remux=[FF,"-nostdin","-hide_banner","-n","-i",str(mkv),"-map","0:v:0",
           "-an","-c:v","copy","-video_track_timescale","16000",
           "-movflags","+faststart",str(clip)]
    trace,res=run("remux-mp4-copy",remux); traces.append(trace)
    if res.returncode:
        return {"method":"mkv_to_mp4_stream_copy","build_traces":traces,"intermediate_sha256":sha(mkv),"error":"remux_failed"}
    return {"method":"mkv_to_mp4_stream_copy","build_traces":traces,"intermediate_sha256":sha(mkv),
            "candidate":evaluate("remux",clip,srcpts,traces)}

def method_vfr(srcpts):
    traces=[]
    clip=DIAG/"vfr.mp4"
    cmd=[FF,"-nostdin","-hide_banner","-n","-i",str(SOURCE),"-map","0:v:0",
         "-vf","select=between(n\\,4258\\,4275),setpts=PTS-STARTPTS",
         "-fps_mode","vfr","-enc_time_base","filter","-video_track_timescale","16000",
         "-an","-c:v","libx264","-crf","12","-pix_fmt","yuv420p",
         "-movflags","+faststart",str(clip)]
    trace,res=run("vfr-encode",cmd); traces.append(trace)
    if res.returncode:
        return {"method":"fps_mode_vfr","build_traces":traces,"error":"encode_failed"}
    return {"method":"fps_mode_vfr","build_traces":traces,
            "candidate":evaluate("vfr",clip,srcpts,traces)}

def method_tail(srcpts):
    traces=[]
    intermediate=DIAG/"tail-19.mkv"
    clip=DIAG/"tail-duration.mp4"
    encode=[FF,"-nostdin","-hide_banner","-n","-i",str(SOURCE),"-map","0:v:0",
            "-vf","select=between(n\\,4258\\,4275),setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop=1",
            "-fps_mode","passthrough","-enc_time_base","filter","-an",
            "-c:v","libx264","-crf","12","-pix_fmt","yuv420p",str(intermediate)]
    trace,res=run("tail-19-encode",encode); traces.append(trace)
    if res.returncode:
        return {"method":"trailing_clone_then_trim_copy","build_traces":traces,"error":"mkv_encode_failed"}
    remux=[FF,"-nostdin","-hide_banner","-n","-i",str(intermediate),"-map","0:v:0",
           "-an","-c:v","copy","-t","0.600","-video_track_timescale","16000",
           "-movflags","+faststart",str(clip)]
    trace,res=run("tail-trim-copy",remux); traces.append(trace)
    if res.returncode:
        return {"method":"trailing_clone_then_trim_copy","build_traces":traces,"intermediate_sha256":sha(intermediate),"error":"trim_remux_failed"}
    return {"method":"trailing_clone_then_trim_copy","build_traces":traces,"intermediate_sha256":sha(intermediate),
            "candidate":evaluate("tail-duration",clip,srcpts,traces)}

mode=sys.argv[1]
if mode=="source":
    source_check()
    print("source_check_ok")
else:
    srcpts=json.loads((DIAG/"source-check.json").read_text())["source_pts"]
    result={"remux":method_remux,"vfr":method_vfr,"tail":method_tail}[mode](srcpts)
    save_json(mode+"-result.json",result)
    c=result.get("candidate",{})
    print(json.dumps({"method":mode,"error":result.get("error"),"candidate_sha256":c.get("sha256"),
                      "decoded_count":c.get("decoded_count"),"strict_native_pts_equal":c.get("strict_native_pts_equal"),
                      "client_probe":c.get("client_probe"),"client_receipt":c.get("client_receipt")}))
