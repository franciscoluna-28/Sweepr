"""Denoising pipeline: ffmpeg decodes and encodes, deep-filter (DeepFilterNet3) enhances.

Every external program is started with an argument list (never through a
shell), and its stdout/stderr go to temp files so a chatty tool cannot deadlock
the server. A cancel event kills the running child immediately.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from . import assets, limits

log = logging.getLogger("sweepr.engine")

_MP4_EXTS = {".mp4", ".mov", ".m4v"}
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Quiet recordings (e.g. camera audio) read as silence to the model, so inputs
# below this RMS are lifted toward it before denoising. Loud inputs are untouched.
TARGET_RMS_DB = -18.0
PEAK_CEILING_DB = -0.09
POST_FILTER_BETA = "0.02"
_LRA = 11.0


class AudioError(Exception):
    """A user-facing validation or processing failure (message is safe to show)."""


class Cancelled(Exception):
    """The job was cancelled; partial output is discarded by the caller."""


def _tools() -> assets.Tools:
    try:
        return assets.resolve_tools()
    except assets.AssetError as exc:
        raise AudioError(str(exc)) from exc


def _tool_env(tool: str) -> dict[str, str] | None:
    """Shared libraries ship next to the tools; make the loader look there too."""
    if sys.platform == "win32":
        return None  # Windows finds DLLs beside the executable
    var = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    env = dict(os.environ)
    here = str(Path(tool).resolve().parent)
    env[var] = here + (os.pathsep + env[var] if env.get(var) else "")
    return env


def _capture(cmd: list[str], cancel: threading.Event | None = None) -> tuple[int, str, str]:
    """Run a tool to completion. Returns (returncode, stdout, stderr)."""
    argv = [str(c) for c in cmd]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            creationflags=_NO_WINDOW,
            env=_tool_env(argv[0]),
        )
        try:
            while True:
                try:
                    code = proc.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    if cancel is not None and cancel.is_set():
                        raise Cancelled() from None
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        out.seek(0)
        err.seek(0)
        return code, out.read().decode("utf-8", "replace"), err.read().decode("utf-8", "replace")


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in limits.VIDEO_EXTS


def _video_out_ext(src: str | Path) -> str:
    return ".mp4" if Path(src).suffix.lower() in _MP4_EXTS else ".mkv"


def _duration_limit_label() -> str:
    h, m = divmod(limits.MAX_DURATION_S // 60, 60)
    return f"{h}h {m}m" if h and m else (f"{h}h" if h else f"{m} minutes")


def probe(path: str | Path) -> dict:
    """Validate a file from its headers (no full decode). Raises AudioError."""
    ffprobe = _tools().ffprobe
    code, out, _ = _capture(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,sample_rate,channels,disposition:format=duration",
            "-of",
            "json",
            path,
        ]
    )
    try:
        data = json.loads(out or "{}")
    except ValueError:
        data = {}
    if code != 0 or not data.get("streams"):
        raise AudioError("not a decodable audio or video file")

    streams = data["streams"]
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if audio is None:
        raise AudioError("contains no audio track")
    # Cover art in MP3/M4A shows up as a video stream; only real video counts.
    has_video = any(
        s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")
        for s in streams
    )
    try:
        sample_rate = int(audio["sample_rate"])
        channels = int(audio["channels"])
        duration = float((data.get("format") or {}).get("duration"))
    except (KeyError, TypeError, ValueError):
        raise AudioError("could not read the audio track") from None

    if sample_rate <= 0 or duration <= 0:
        raise AudioError("contains no audio data")
    if not limits.MIN_SAMPLE_RATE <= sample_rate <= limits.MAX_SAMPLE_RATE:
        raise AudioError(f"unsupported sample rate {sample_rate} Hz")
    if channels > limits.MAX_CHANNELS:
        raise AudioError(f"{channels} channels not supported (mono or stereo only)")
    if duration > limits.MAX_DURATION_S:
        raise AudioError(f"longer than {_duration_limit_label()}")
    return {
        "sample_rate": sample_rate,
        "num_frames": int(duration * sample_rate),
        "channels": channels,
        "duration": duration,
        "is_video": _is_video(path),
        "has_video": has_video and _is_video(path),
    }


def _extract_wav(src: str, dst: Path, cancel: threading.Event | None) -> None:
    code, _, _ = _capture(
        [
            _tools().ffmpeg,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-i",
            src,
            "-map",
            "0:a:0",
            "-vn",
            # deep-filter reads 16-bit int or 32-bit float WAV only; float keeps full precision.
            "-c:a",
            "pcm_f32le",
            dst,
        ],
        cancel,
    )
    if code != 0 or not dst.is_file():
        raise AudioError("could not read the audio from this file")


def _quiet_gain_db(wav: Path, cancel: threading.Event | None) -> float:
    """How many dB to lift a quiet input (0 if it is already loud enough)."""
    _, _, err = _capture(
        [_tools().ffmpeg, "-hide_banner", "-nostdin", "-i", wav, "-af", "volumedetect", "-f", "null", "-"],
        cancel,
    )
    mean = _grab_db(err, "mean_volume")
    peak = _grab_db(err, "max_volume")
    if mean is None or peak is None or mean >= TARGET_RMS_DB:
        return 0.0
    return max(0.0, min(TARGET_RMS_DB - mean, PEAK_CEILING_DB - peak))


def _grab_db(text: str, key: str) -> float | None:
    match = re.search(rf"{key}:\s*(-?[\d.]+|-inf) dB", text)
    if not match or match.group(1) == "-inf":
        return None
    return float(match.group(1))


def _apply_gain(src: Path, dst: Path, db: float, cancel: threading.Event | None) -> None:
    code, _, _ = _capture(
        [
            _tools().ffmpeg,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-i",
            src,
            "-af",
            f"volume={db:.3f}dB",
            "-c:a",
            "pcm_f32le",
            dst,
        ],
        cancel,
    )
    if code != 0:
        raise AudioError("could not adjust the input level")


def _denoise(wav: Path, out_dir: Path, settings: dict, cancel: threading.Event | None) -> Path:
    cmd: list[str | Path] = [
        _tools().deep_filter,
        "-a",
        f"{float(settings['atten_lim_db']):g}",
        "-D",
        "-o",
        out_dir,
    ]
    if settings.get("post_filter"):
        cmd += ["--pf", "--pf-beta", POST_FILTER_BETA]
    cmd.append(wav)
    code, _, err = _capture(cmd, cancel)
    result = out_dir / wav.name
    if code != 0 or not result.is_file():
        log.error("deep-filter failed (exit %s): %s", code, err.strip()[-500:])
        raise AudioError("the denoiser could not process this file")
    return result


def _to_pcm24(src: Path, dst: Path, sample_rate: int, cancel: threading.Event | None) -> None:
    code, _, _ = _capture(
        [_tools().ffmpeg, "-y", "-nostdin", "-hide_banner", "-i", src, "-ar", str(sample_rate), "-c:a", "pcm_s24le", dst],
        cancel,
    )
    if code != 0 or not dst.is_file():
        raise AudioError("could not write the enhanced audio")


def _normalize_wav(path: Path, sr: int, target_lufs: float, tp_dbtp: float) -> tuple[float, float]:
    """Rewrite a WAV in place to a target integrated loudness (EBU R128).

    Two-pass ffmpeg loudnorm: measure, then apply one linear gain with a
    true-peak ceiling. Returns (lufs_before, lufs_after); NaN if unmeasurable.
    """
    ffmpeg = _tools().ffmpeg
    _, _, text = _capture(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-i",
            path,
            "-af",
            f"loudnorm=I={target_lufs}:TP={tp_dbtp}:LRA={_LRA}:print_format=json",
            "-f",
            "null",
            "-",
        ]
    )
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise AudioError("could not measure loudness for normalization")
    try:
        measured = json.loads(text[start : end + 1])
    except ValueError:
        raise AudioError("could not measure loudness for normalization") from None

    def value(key: str) -> float:
        try:
            v = float(measured[key])
        except (KeyError, TypeError, ValueError):
            return float("nan")
        return v if math.isfinite(v) else float("nan")

    before, after = value("input_i"), value("output_i")
    tmp = path.with_name(path.name + ".norm.wav")
    code, _, _ = _capture(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i",
            path,
            "-af",
            (
                f"loudnorm=I={target_lufs}:TP={tp_dbtp}:LRA={_LRA}"
                f":measured_I={measured.get('input_i')}"
                f":measured_TP={measured.get('input_tp')}"
                f":measured_LRA={measured.get('input_lra')}"
                f":measured_thresh={measured.get('input_thresh')}"
                f":offset={measured.get('target_offset')}"
                ":linear=true"
            ),
            "-ar",
            str(sr),
            "-c:a",
            "pcm_s24le",
            tmp,
        ]
    )
    if code != 0 or not tmp.is_file():
        raise AudioError("could not normalize loudness")
    tmp.replace(path)
    return before, after


def _mux_video(video_src: str, enhanced_wav: Path, dst: Path, cancel: threading.Event | None) -> None:
    """Copy the original video stream and replace its audio with the enhanced WAV."""
    cmd: list[str | Path] = [
        _tools().ffmpeg,
        "-y",
        "-nostdin",
        "-hide_banner",
        "-i",
        video_src,
        "-i",
        enhanced_wav,
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
    ]
    if dst.suffix.lower() == ".mp4":
        cmd += ["-movflags", "+faststart"]
    cmd.append(dst)
    code, _, _ = _capture(cmd, cancel)
    if code != 0 or not dst.is_file():
        raise AudioError("could not write the video with enhanced audio")


def process_file(src: str | Path, dst: str | Path, settings: dict, cancel: threading.Event | None = None) -> dict:
    """Denoise one file into a 24-bit WAV at the source sample rate.

    When ``settings["normalize"]`` is set the WAV is loudness-normalized before
    any video mux. Returns the muxed ``video`` path (or None) and the measured
    ``lufs_before`` / ``lufs_after`` (None when normalization is off).
    """
    src = str(src)
    dst = Path(dst)
    info = probe(src)
    with tempfile.TemporaryDirectory(prefix="sweepr-") as tmp_name:
        tmp = Path(tmp_name)
        wav = tmp / "input.wav"
        _extract_wav(src, wav, cancel)
        _check_cancel(cancel)

        gain = _quiet_gain_db(wav, cancel)
        if gain > 0.0:
            lifted = tmp / "lifted.wav"
            _apply_gain(wav, lifted, gain, cancel)
            wav = lifted
        _check_cancel(cancel)

        out_dir = tmp / "enhanced"
        out_dir.mkdir()
        enhanced = _denoise(wav, out_dir, settings, cancel)
        _check_cancel(cancel)
        _to_pcm24(enhanced, dst, info["sample_rate"], cancel)

    lufs_before = lufs_after = None
    if settings.get("normalize"):
        _check_cancel(cancel)
        lufs_before, lufs_after = _normalize_wav(
            dst, info["sample_rate"], float(settings["target_lufs"]), limits.DEFAULT_TRUE_PEAK_DBTP
        )

    result: dict = {"video": None, "lufs_before": _finite(lufs_before), "lufs_after": _finite(lufs_after)}
    if info["has_video"]:
        _check_cancel(cancel)
        video_dst = dst.with_suffix(_video_out_ext(src))
        _mux_video(src, dst, video_dst, cancel)
        result["video"] = video_dst
    return result


def _finite(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value
