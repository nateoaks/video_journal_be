"""Compilation pipeline: render ordered, trimmed clips + soundtrack to MP4."""

from collections.abc import Callable
from dataclasses import dataclass

from app.media.ffmpeg import run_ffmpeg_with_progress


@dataclass
class ClipSpec:
    """Describes a single clip's contribution to a compilation."""

    path: str
    trim_in_s: float
    trim_out_s: float


def build_compile_command(
    clip_specs: list[ClipSpec],
    soundtrack_path: str,
    output_path: str,
    soundtrack_fade_start_s: float,
    mix_clip_audio: bool = False,
    clip_audio_volume: float = 0.4,
) -> list[str]:
    """Return the ffmpeg argument list for rendering a compilation.

    Each clip uses input seek (-ss/-to before -i) for fast, accurate trimming
    of pre-normalised CFR inputs.  The video segments are concatenated; the
    soundtrack gets a 2-second fade-out.

    When mix_clip_audio is False (default) the soundtrack is used as the sole
    audio track, preserving byte-for-byte identical output to the original
    behaviour.  When True, clip audio streams are concatenated and mixed under
    the soundtrack via amix, with clip_audio_volume controlling the clip weight.
    """
    args: list[str] = ["ffmpeg", "-y"]

    # Per-clip inputs with input seek.
    for spec in clip_specs:
        args += [
            "-ss",
            str(spec.trim_in_s),
            "-to",
            str(spec.trim_out_s),
            "-i",
            spec.path,
        ]

    # Soundtrack input (no seek; full file used).
    args += ["-i", soundtrack_path]

    n = len(clip_specs)
    soundtrack_index = n  # 0..n-1 are clips; n is soundtrack

    # Video concat filter.
    concat_inputs = "".join(f"[{i}:v]" for i in range(n))
    concat_filter = f"{concat_inputs}concat=n={n}:v=1:a=0[vout]"

    # Soundtrack fade-out filter.
    fade_filter = (
        f"[{soundtrack_index}:a]afade=t=out:st={soundtrack_fade_start_s}:d=2[aout]"
    )

    if not mix_clip_audio:
        # Default path: soundtrack only, output mapped from [aout].
        filter_complex = f"{concat_filter};{fade_filter}"
        audio_map = "[aout]"
    else:
        # Mix path: concat clip audio streams then amix with faded soundtrack.
        clip_audio_inputs = "".join(f"[{i}:a]" for i in range(n))
        clip_audio_concat = f"{clip_audio_inputs}concat=n={n}:v=0:a=1[clipaud]"
        mix_filter = (
            f"[aout][clipaud]amix=inputs=2:duration=first"
            f":weights=1 {clip_audio_volume:.4f}:dropout_transition=0[mixout]"
        )
        filter_complex = (
            f"{concat_filter};{fade_filter};{clip_audio_concat};{mix_filter}"
        )
        audio_map = "[mixout]"

    args += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        audio_map,
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "-shortest",
        "-stats_period",
        "0.5",
        "-progress",
        "pipe:1",
        output_path,
    ]

    return args


async def compile_video(
    clip_specs: list[ClipSpec],
    soundtrack_path: str,
    output_path: str,
    total_duration_s: float,
    on_progress: Callable[[int], None] | None = None,
    mix_clip_audio: bool = False,
    clip_audio_volume: float = 0.4,
) -> None:
    """Render a compilation to output_path.

    Calls on_progress(out_time_us) for each progress tick when provided.
    Raises FfmpegError on failure.
    """
    fade_start = max(0.0, total_duration_s - 2.0)
    args = build_compile_command(
        clip_specs,
        soundtrack_path,
        output_path,
        fade_start,
        mix_clip_audio=mix_clip_audio,
        clip_audio_volume=clip_audio_volume,
    )
    await run_ffmpeg_with_progress(args, on_progress=on_progress)
