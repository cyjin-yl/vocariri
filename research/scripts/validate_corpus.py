#!/usr/bin/env python3
"""Check evidence gates and segment identity in corpus.jsonl."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "corpus.jsonl"
ORDER = ["discovered_video", "discovered_source", "metadata_only_candidate", "frame_inspected_segment", "motion_verified_segment", "source_inspected_form", "form_verified", "reviewed_sample"]
VIDEO_STATES = {"discovered_video", "frame_inspected_segment", "motion_verified_segment"}


def validate(row, line):
    errors = []
    state = row.get("evidence_state")
    if state not in ORDER:
        return [f"line {line}: invalid evidence_state"]
    if not row.get("source_url") or not row.get("evidence"):
        errors.append(f"line {line}: source_url and evidence are required")
    if row.get("source_kind") not in {"public_video", "animation_template", "tutorial", "editable_project", "other_public_demo"}:
        errors.append(f"line {line}: invalid source_kind")
    if row.get("domain_specificity") not in {"generic_motion_mechanism", "lyric_video_context_candidate", "vocaloid_pv_visual_observed"}:
        errors.append(f"line {line}: invalid or missing domain_specificity")
    if state in VIDEO_STATES and row.get("source_kind") != "public_video":
        errors.append(f"line {line}: video evidence state requires public_video source_kind")
    if state == "discovered_source" and row.get("source_kind") == "public_video":
        errors.append(f"line {line}: use discovered_video for a public_video source")
    if state == "discovered_video" and row.get("source_kind") != "public_video":
        errors.append(f"line {line}: use discovered_source for a non-video source")
    if state in {"discovered_video", "discovered_source", "metadata_only_candidate"} and not row.get("evidence"):
        errors.append(f"line {line}: discovery/candidate state requires linked source evidence")
    if state in {"frame_inspected_segment", "motion_verified_segment"}:
        frames = [e for e in row.get("evidence", []) if e.get("kind") == "frame" and e.get("observed_time_seconds") is not None]
        if not frames:
            errors.append(f"line {line}: frame evidence with observed time required")
    if state == "motion_verified_segment":
        intervals = [e for e in row.get("evidence", []) if e.get("kind") == "video_interval"]
        if not intervals or row.get("segment_start_seconds") is None or row.get("segment_end_seconds") is None:
            errors.append(f"line {line}: motion evidence and observed interval required")
        elif row["segment_end_seconds"] <= row["segment_start_seconds"]:
            errors.append(f"line {line}: segment end must exceed start")
    if state == "source_inspected_form":
        kinds = {e.get("kind") for e in row.get("evidence", [])}
        if not kinds.intersection({"template_preview", "tutorial_step", "project_file", "public_demo"}):
            errors.append(f"line {line}: source_inspected_form requires a non-video source artifact")
    if state == "form_verified" and not row.get("form_id"):
        errors.append(f"line {line}: form_verified requires form_id")
    if state == "reviewed_sample" and not row.get("review"):
        errors.append(f"line {line}: review record required")
    return errors


def main():
    errors = []
    seen = set()
    sample_ids = set()
    form_ids = set()
    rows = []
    for number, raw in enumerate(PATH.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"line {number}: invalid JSON ({exc.msg})")
            continue
        rows.append(row)
        errors.extend(validate(row, number))
        if row.get("sample_id") in sample_ids:
            errors.append(f"line {number}: duplicate sample_id")
        sample_ids.add(row.get("sample_id"))
        if row.get("form_id"):
            if row["form_id"] in form_ids:
                errors.append(f"line {number}: duplicate form_id; merge evidence/variants under one form")
            form_ids.add(row["form_id"])
        if row.get("source_kind") == "public_video" and row.get("segment_start_seconds") is not None and row.get("segment_end_seconds") is not None:
            key = (row.get("video_platform_id") or row.get("source_url"), row["segment_start_seconds"], row["segment_end_seconds"])
            if key in seen:
                errors.append(f"line {number}: duplicate video/time interval")
            seen.add(key)
    counts = {state: sum(r.get("evidence_state") == state for r in rows) for state in ORDER}
    print(json.dumps({"rows": len(rows), "counts": counts, "errors": errors}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
