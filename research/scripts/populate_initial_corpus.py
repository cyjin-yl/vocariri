#!/usr/bin/env python3
"""Append the hand-reviewed source-code forms and Bilibili metadata candidates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus.jsonl"

USE_URL = "https://registry.npmjs.org/usetypoui/-/usetypoui-1.0.1.tgz"
USE_HASH = "f08e5b8680596e28a186947866e72fa2e17c49f4086f12114ae614fbee457671"
USE_TIME = "2026-09-24T00:27:42.497708+00:00"
PRES_URL = "https://registry.npmjs.org/%40pyreon%2Fkinetic-presets/-/kinetic-presets-0.51.0.tgz"
PRES_HASH = "6940bb6fb2165a737fa6114959ab4a668b151f3c67a580e7f3c9cd7765d26fcf"
PRES_TIME = "2026-09-24T00:33:19.150129+00:00"
REM_URL = "https://registry.npmjs.org/%40remotion%2Ftransitions/-/transitions-4.0.527.tgz"
REM_HASH = "821e1993474f5fc0deba45fccdb8758248326eb6b1465a618cc0613ec1891514"
REM_TIME = "2026-09-24T00:31:15.090921+00:00"


def ev(url, digest, retrieved, member, kind="public_demo"):
    return {"url": url, "kind": kind, "observed_time_seconds": None,
            "sha256": digest, "retrieved_utc": retrieved, "artifact_member": member}


def form(sample_id, form_id, package_url, member, digest, retrieved, tags, motion,
         variants=None, extra_evidence=None, layering=None):
    evidence = [ev(package_url, digest, retrieved, member, "public_demo")]
    evidence.extend(extra_evidence or [])
    return {
        "sample_id": sample_id,
        "source_url": package_url,
        "source_kind": "other_public_demo",
        "domain_specificity": "generic_motion_mechanism",
        "form_id": form_id,
        "variant_parameters": variants or {},
        "evidence_state": "source_inspected_form",
        "segment_start_seconds": None,
        "segment_end_seconds": None,
        "effect_tags": tags,
        "transition_in": None,
        "transition_out": None,
        "layering": layering or ["per-character text style output"],
        "motion_description": motion,
        "unknowns": ["Published code was inspected; no rendered preview or music synchronization was inspected. This generic mechanism is not attributed to any named VOCALOID PV."],
        "evidence": evidence,
    }


def candidate(sample_id, bvid, title, page_hash=None, page_time=None,
              search_hash=None, search_time=None, search_url=None, thumbnail=None):
    page_url = f"https://www.bilibili.com/video/{bvid}/"
    evidence = []
    if page_hash:
        evidence.append(ev(page_url, page_hash, page_time, None, "video_page"))
    if search_hash:
        evidence.append(ev(search_url, search_hash, search_time, None, "catalog"))
    if thumbnail:
        evidence.append(ev(thumbnail[0], thumbnail[1], thumbnail[2], None, "thumbnail"))
    return {
        "sample_id": sample_id,
        "source_url": page_url,
        "source_kind": "public_video",
        "domain_specificity": "lyric_video_context_candidate",
        "form_id": None,
        "variant_parameters": {},
        "video_title": title,
        "video_platform_id": bvid,
        "evidence_state": "metadata_only_candidate",
        "segment_start_seconds": None,
        "segment_end_seconds": None,
        "effect_tags": ["candidate-only", "not-motion-verified"],
        "transition_in": None,
        "transition_out": None,
        "layering": [],
        "motion_description": None,
        "unknowns": ["Only public title/page metadata was inspected. Video playback, timestamps, transitions, and effect behavior remain unknown."],
        "evidence": evidence,
    }


def build_rows():
    u = "package/dist/index.mjs"
    p = "package/lib/index.js"
    r = "package/dist/presentations/"
    rows = []
    use_forms = [
        ("type-on", ["typewriter"], ["glyph-reveal", "threshold"], "Characters appear in index order at a progress threshold; the code may substitute a brief random glyph near the active boundary."),
        ("handwriting-path", ["handwriting"], ["glyph-reveal", "drift", "rotation"], "Each character follows a small time-varying x/y offset and rotation while opacity and scale rise."),
        ("glitch", ["glitch"], ["random-offset", "rgb-split", "glyph-substitution"], "Characters intermittently jump with random offsets/skew, color changes, text-shadow separation, and optional character substitution."),
        ("scramble-settle", ["scramble"], ["random-glyph", "settling"], "Characters are replaced by random symbols until their per-character progress passes a settle threshold."),
        ("morse-pulse", ["morse"], ["binary-pulse", "character-stagger"], "Character opacity follows a repeated on/off pulse pattern, staggered by character position."),
        ("matrix-symbol-stream", ["matrix"], ["symbol-substitution", "green-glow", "stagger"], "A staggered character sequence cycles through symbols, then resolves while its color and glow change."),
        ("glyph-wave", ["wave"], ["sinusoidal-path", "rotation", "stagger"], "Per-character phase drives a vertical sine offset and a smaller sine-driven rotation."),
        ("center-out-ripple", ["rippletext"], ["center-out", "spring-settle"], "A center-distance delay produces a symmetric per-character bounce/scale reveal that travels outward."),
        ("cursor-force", ["magnetic"], ["pointer-reactive", "distance-field"], "Character centers receive a distance-attenuated vector offset from the cursor position."),
        ("orbit-path", ["orbit"], ["elliptical-path", "stagger"], "Per-character phase traces an outward elliptical orbit as the entrance settles."),
        ("pendulum-rotation", ["pendulum"], ["oscillation", "rotation", "damping"], "Characters rotate with a damped sinusoid whose envelope decreases through the entrance."),
        ("radial-split", ["split"], ["radial-trajectory", "rotation", "opacity"], "Characters travel along index-seeded radial angles while rotating and fading toward their resting positions."),
        ("radial-shatter", ["shatter"], ["staged-disassembly", "radial-trajectory", "rotation"], "After a hold, characters move on seeded radial directions, rotate, shrink, and fade out."),
        ("perspective-fold", ["origami"], ["perspective", "rotate-y", "glyph-stagger"], "Characters fold around the y axis under perspective while scaling into their resting size."),
        ("liquid-wobble", ["liquid"], ["wobble", "nonuniform-scale", "blur"], "Time and character index perturb x/y scale and vertical position, with blur/opacity clearing during the reveal."),
        ("spectrum-sweep", ["rainbow"], ["per-character-hue", "vertical-offset"], "Character-index hue and time determine a moving color spectrum alongside a small vertical entry offset."),
        ("neon-flicker", ["neon"], ["emissive-pulse", "flicker", "glow"], "Characters gate opacity with an index/time pulse and animate multi-radius text shadows as a neon glow."),
        ("directional-slide", ["slide"], ["translation", "stagger", "opacity"], "A character-index-signed horizontal translation closes toward the baseline while opacity rises; scene-level slide presets are a scope variant."),
        ("scale-entry", ["scale"], ["scale", "stagger", "opacity"], "Characters scale from a smaller source size toward one with staggered progress; Pyreon supplies whole-element scale presets."),
        ("overshoot-pop", ["pop", "elastic", "spring"], ["overshoot", "scale", "settling"], "Entry scale overshoots or oscillates before settling; bounce/spring names with amplitude or easing changes are retained as variants."),
        ("gravity-drop", ["gravity"], ["falling-trajectory", "rotation", "settling"], "Characters enter from a large vertical offset with alternating rotation and an eased landing."),
    ]
    for index, (form_name, routines, tags, description) in enumerate(use_forms, 1):
        extra = []
        variants = {"routine_names": routines, "scope": "character"}
        if form_name == "directional-slide":
            extra.append(ev(PRES_URL, PRES_HASH, PRES_TIME, p, "public_demo"))
            extra.append(ev(REM_URL, REM_HASH, REM_TIME, r + "slide.js", "public_demo"))
            variants["scope_variants"] = ["glyph", "whole scene"]
        if form_name == "scale-entry":
            extra.append(ev(PRES_URL, PRES_HASH, PRES_TIME, p, "public_demo"))
        if form_name == "overshoot-pop":
            extra.append(ev(PRES_URL, PRES_HASH, PRES_TIME, p, "public_demo"))
        rows.append(form(f"code-form-{index:02d}", f"text.{form_name}", USE_URL, u, USE_HASH, USE_TIME,
                         tags, description, variants, extra))

    scene_forms = [
        ("crossfade", "fade.js", ["opacity-interpolation", "scene-transition"], "The entering scene opacity follows progress; exiting scene opacity may use the inverse progress."),
        ("shape-matte-wipe", "wipe.js", ["polygon-clip", "directional-mask"], "A progress-scaled polygon clip reveals the next scene from an edge or corner; Pyreon clip-path presets provide inset, circle, and diamond variants."),
        ("radial-iris", "iris.js", ["circle-mask", "radial-reveal"], "A circle path grows from zero radius to a diagonal-covering radius and clips the entering scene."),
        ("clock-wedge", "clock-wipe.js", ["pie-mask", "radial-sweep"], "A pie-shaped path grows with progress to reveal the entering scene like a clock hand sweep."),
        ("noise-dissolve", "dissolve.js", ["shader", "noise-threshold", "edge-color"], "A fragment shader compares a noise field to progress and exposes configurable hot/spread edge colors."),
        ("ripple-displacement", "ripple.js", ["shader", "uv-displacement", "sine-wave"], "A radial sine term offsets image sampling coordinates while the old/new scene mix changes over progress."),
        ("film-burn", "film-burn.js", ["shader", "seeded-noise", "color-burn"], "A seeded fragment-shader pattern produces a film-burn-like transition; seed is an explicit variant parameter."),
        ("book-page-fold", "book-flip.js", ["shader", "projective-fold", "page-turn"], "A directional fragment-shader fold skews page coordinates and maps the old/new scenes across a turning surface."),
        ("push-cut-flash", "push-cut.js", ["scale-push", "hard-cut", "flash"], "A composed transition pushes/scales outgoing and incoming scenes around a discrete cut with a short configurable flash."),
    ]
    for index, (form_name, filename, tags, description) in enumerate(scene_forms, 22):
        extra = []
        variants = {"scope": "whole scene", "module": filename}
        if form_name == "shape-matte-wipe":
            extra.append(ev(PRES_URL, PRES_HASH, PRES_TIME, p, "project_file"))
        rows.append(form(f"code-form-{index:02d}", f"scene.{form_name}", REM_URL, r + filename,
                         REM_HASH, REM_TIME, tags, description, variants, extra,
                         ["incoming scene", "outgoing scene", "transition mask/composite"]))

    preset_forms = [
        ("perspective-slit", "perspective/slitHorizontal/slitVertical", ["perspective", "hinge", "aperture"], "A narrow horizontal or vertical slit opens as a perspective hinge rotates and the element expands."),
        ("skewed-fly-in", "lightSpeedInLeft/lightSpeedInRight", ["skew", "directional-translation", "opacity"], "A large lateral translation enters while skew decays to zero, combining speed-line direction with an opacity reveal."),
    ]
    for index, (form_name, member, tags, description) in enumerate(preset_forms, 31):
        rows.append(form(f"code-form-{index:02d}", f"scene.{form_name}", PRES_URL, p,
                         PRES_HASH, PRES_TIME, tags, description,
                         {"preset_family": member, "direction_and_timing": "variants collapsed"},
                         layering=["whole-element transform", "opacity/clip style"]))

    candidate_rows = [
        candidate("video-candidate-01", "BV1ZQBrBGE3A", "术イ口视频制作教程", "75414fe2510ecee70a5510aa04056a4cf9faa0cae811e0d472f5d151ca7be320", "2026-09-24T00:37:05.251332+00:00", thumbnail=("https://i1.hdslb.com/bfs/archive/4bd82408d3de16cc47fc40fee9b3eb771f63020c.jpg", "fa340c57d3265ea3307be4c879ef953884dde355f464b819849c70a62ac12bf4", "2026-09-24T00:39:36.363871+00:00")),
        candidate("video-candidate-02", "BV19f4y1Q7YF", "动词打次-歌词动画/PV/Lyric Video 生成与创作工具", "2120f92c8a97ec952cdbc4a477279e848cf1620fde521633149c3854e2a5bc9f", "2026-09-24T00:41:28.275399+00:00"),
        candidate("video-candidate-03", "BV1sQhFziEwT", "AE模板|说唱音乐动态歌词排版动画 Lyric Video", "12158c2e2ed2100aa53190b182c887e55e3ffacfe5b50a62383a7da6dd14f6a7", "2026-09-24T00:45:24.888369+00:00", thumbnail=("https://i0.hdslb.com/bfs/archive/df8f3d2521eb494db373504ca42ae1901ebc0f96.jpg", "0a8eedbb11b8b23ea4e83626301bb647cf62c59cafee41730c19d9f83bc8f968", "2026-09-24T00:48:26.592759+00:00")),
        candidate("video-candidate-04", "BV1Xc8E6JEvf", "AE制作文字歌词练习动画源文件", "e72e73e58e2b85ab51cdd433834bbde8e9622af8c9e27f3826876bead1d3c83d", "2026-09-24T00:45:59.819565+00:00"),
        candidate("video-candidate-05", "BV1QZ421W7Pm", "【AE教程】快速导入音乐歌词做文字pv或mv动画演示", "1ca03a8084972a79edeb1b08849c7291f5e675a5f0df2b4cfba6111702dd36aa", "2026-09-24T00:46:29.775755+00:00"),
        candidate("video-candidate-06", "BV13bAuzKEz3", "【文字PV效果教程】PV TOOL + NOW PLAYING + SHOOST", "83a659d7d8b977e096eb8cdbcedfa37a449229ac34e779e8847220b6ef007fb4", "2026-09-24T00:46:47.184157+00:00"),
        candidate("video-candidate-07", "BV1qf4y117Wf", "【AE教程】mojito MV 字幕动画效果制作分享！", search_hash="1d91b24b65de16378004b268458dbe3406c2cc21f5683eefb7b49a8e055d337d", search_time="2026-09-24T00:44:58.191504+00:00", search_url="https://search.bilibili.com/all?keyword=AE%20%E6%96%87%E5%AD%97PV%E6%95%99%E7%A8%8B%20%E6%AD%8C%E8%AF%8D%E5%8A%A8%E7%94%BB"),
        candidate("video-candidate-08", "BV1VoeJ6iEpy", "《恋》但是仿wowaka式PV（？）", search_hash="63adc4e24e5252351c404d690eb0785452ce1d12ac9e84a99f18d14280453f9d", search_time="2026-09-24T00:34:35.636644+00:00", search_url="https://search.bilibili.com/all?keyword=VOCALOID%20PV%20%E5%AD%97%E5%B9%95%E5%8A%A8%E7%94%BB%20%E5%88%B6%E4%BD%9C%E6%95%99%E7%A8%8B"),
        candidate("video-candidate-09", "BV1zrbCzLEH4", "【4K 60帧】初音未来的消失MV 中日双语版", search_hash="63adc4e24e5252351c404d690eb0785452ce1d12ac9e84a99f18d14280453f9d", search_time="2026-09-24T00:34:35.636644+00:00", search_url="https://search.bilibili.com/all?keyword=VOCALOID%20PV%20%E5%AD%97%E5%B9%95%E5%8A%A8%E7%94%BB%20%E5%88%B6%E4%BD%9C%E6%95%99%E7%A8%8B"),
        candidate("video-candidate-10", "BV1k72LYzEmV", "【エスプリ企划】スキスキハンター♡ feat.初音ミク 官方文字PV", search_hash="63adc4e24e5252351c404d690eb0785452ce1d12ac9e84a99f18d14280453f9d", search_time="2026-09-24T00:34:35.636644+00:00", search_url="https://search.bilibili.com/all?keyword=VOCALOID%20PV%20%E5%AD%97%E5%B9%95%E5%8A%A8%E7%94%BB%20%E5%88%B6%E4%BD%9C%E6%95%99%E7%A8%8B"),
    ]
    rows.extend(candidate_rows)
    return rows


def main():
    if CORPUS.stat().st_size:
        raise SystemExit("corpus.jsonl is non-empty; refusing to append duplicate initial rows")
    rows = build_rows()
    with CORPUS.open("a", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"rows_written": len(rows), "source_inspected_forms": sum(r["evidence_state"] == "source_inspected_form" for r in rows), "metadata_only_video_candidates": sum(r["evidence_state"] == "metadata_only_candidate" for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
