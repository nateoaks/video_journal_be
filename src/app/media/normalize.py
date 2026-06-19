"""Video normalisation: transcode to a canonical H.264/AAC MP4."""

from app.media.ffmpeg import run_ffmpeg


def build_normalize_command(src: str, dst: str) -> list[str]:
    """Return the ffmpeg arg list for the canonical normalisation recipe.

    Output: 1920x1080 (letterboxed), yuv420p, H.264 CRF 18,
    30 fps CFR, AAC 192 kbps stereo, faststart.
    """
    return [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-vf",
        (
            "scale=w=1920:h=1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        ),
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-vsync",
        "cfr",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        dst,
    ]


async def normalize(src: str, dst: str) -> None:
    """Transcode src to dst using the canonical normalisation recipe."""
    await run_ffmpeg(build_normalize_command(src, dst))
