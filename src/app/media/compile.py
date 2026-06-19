"""Compilation pipeline: render ordered, trimmed clips + soundtrack to MP4."""

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
) -> list[str]:
    """Return the ffmpeg argument list for rendering a compilation.

    Each clip uses input seek (-ss/-to before -i) for fast, accurate trimming
    of pre-normalised CFR inputs.  The video segments are concatenated; the
    soundtrack gets a 2-second fade-out and is used as the sole audio track.
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

    filter_complex = f"{concat_filter};{fade_filter}"

    args += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "-shortest",
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
) -> None:
    """Render a compilation to output_path.

    Raises FfmpegError on failure.
    """
    fade_start = max(0.0, total_duration_s - 2.0)
    args = build_compile_command(clip_specs, soundtrack_path, output_path, fade_start)
    await run_ffmpeg_with_progress(args)
