"""Keep spatial and temporal video sampling budgets explicit and independent."""
import math


def video_input_policy(width, height, frames=32, long_edge=768):
    for name, value in (("width", width), ("height", height),
                        ("frames", frames), ("long_edge", long_edge)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if frames < 2 or long_edge < 32:
        raise ValueError("Video sampling needs at least two frames and a 32px long edge")
    scale = min(1.0, long_edge / max(width, height))
    # Qwen3-VL uses 16px patches and 2x spatial merging. Round the intended
    # dimensions to that lattice, and budget the WHOLE video, not one frame.
    target_width = max(32, round(width * scale / 32) * 32)
    target_height = max(32, round(height * scale / 32) * 32)
    even_frames = math.ceil(frames / 2) * 2
    pixels_per_frame = max(4096, target_width * target_height)
    return {
        "media_io_kwargs": {"video": {"num_frames": frames}},
        "mm_processor_kwargs": {
            "do_sample_frames": False,
            "size": {
                "shortest_edge": 4096,
                "longest_edge": even_frames * pixels_per_frame,
            },
        },
        "audit": {
            "source_dimensions": [width, height],
            "requested_frames": frames,
            "target_dimensions": [target_width, target_height],
            "pixels_per_frame_budget": pixels_per_frame,
            "whole_video_pixel_budget": even_frames * pixels_per_frame,
            "note": "CPU-tested budget policy; actual processor dimensions must be checked after model/template changes.",
        },
    }
