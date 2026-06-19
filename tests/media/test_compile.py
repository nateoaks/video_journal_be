"""Unit tests for app.media.compile."""

from app.media.compile import ClipSpec, build_compile_command


def _make_specs(n: int = 2) -> list[ClipSpec]:
    return [
        ClipSpec(path=f"clip{i}.mp4", trim_in_s=float(i), trim_out_s=float(i + 5))
        for i in range(n)
    ]


def test_build_compile_command_starts_with_ffmpeg() -> None:
    specs = _make_specs(1)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 3.0)
    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd


def test_build_compile_command_per_input_seek() -> None:
    """Each clip has -ss and -to placed immediately before its -i."""
    specs = _make_specs(2)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 8.0)

    for spec in specs:
        # Find where this clip's path appears in the command list.
        path_idx = cmd.index(spec.path)
        # Layout is: [-ss, trim_in, -to, trim_out, -i, path]
        assert cmd[path_idx - 5] == "-ss"
        assert cmd[path_idx - 4] == str(spec.trim_in_s)
        assert cmd[path_idx - 3] == "-to"
        assert cmd[path_idx - 2] == str(spec.trim_out_s)
        assert cmd[path_idx - 1] == "-i"


def test_build_compile_command_concat_filter() -> None:
    """filter_complex includes concat=n=N:v=1:a=0."""
    specs = _make_specs(3)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 14.0)
    fc_idx = cmd.index("-filter_complex")
    fc = cmd[fc_idx + 1]
    assert "concat=n=3:v=1:a=0" in fc


def test_build_compile_command_afade_out() -> None:
    """filter_complex includes afade=t=out."""
    specs = _make_specs(2)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 8.0)
    fc_idx = cmd.index("-filter_complex")
    fc = cmd[fc_idx + 1]
    assert "afade=t=out" in fc


def test_build_compile_command_fade_start_for_known_trims() -> None:
    """build_compile_command passes the given fade_start directly into afade."""
    # The compile_video wrapper computes total - 2; here we pass 8.0 directly.
    specs = _make_specs(2)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 8.0)
    fc_idx = cmd.index("-filter_complex")
    fc = cmd[fc_idx + 1]
    assert "st=8.0" in fc or "st=8" in fc


def test_build_compile_command_soundtrack_only_audio() -> None:
    """The soundtrack is the only audio source (via [aout])."""
    specs = _make_specs(2)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 8.0)
    assert "track.mp3" in cmd
    fc_idx = cmd.index("-filter_complex")
    fc = cmd[fc_idx + 1]
    # Soundtrack is the last input, index == len(specs)
    assert f"[{len(specs)}:a]afade" in fc


def test_build_compile_command_libx264_crf18_aac_faststart() -> None:
    """Output codec settings are correct."""
    specs = _make_specs(1)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 5.0)
    assert "libx264" in cmd
    assert "-crf" in cmd
    crf_idx = cmd.index("-crf")
    assert cmd[crf_idx + 1] == "18"
    assert "aac" in cmd
    assert "+faststart" in cmd


def test_build_compile_command_shortest_and_progress() -> None:
    """-shortest and -progress pipe:1 are present."""
    specs = _make_specs(1)
    cmd = build_compile_command(specs, "track.mp3", "out.mp4", 5.0)
    assert "-shortest" in cmd
    assert "-progress" in cmd
    progress_idx = cmd.index("-progress")
    assert cmd[progress_idx + 1] == "pipe:1"


def test_build_compile_command_output_path_last_positional() -> None:
    """The output path appears at the end."""
    specs = _make_specs(1)
    output = "out.mp4"
    cmd = build_compile_command(specs, "track.mp3", output, 5.0)
    assert cmd[-1] == output
