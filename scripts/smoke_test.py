"""End-to-end smoke test for Sweepr.

Covers the engine (decode, denoise, normalize, video mux, cancel), the job API
(validation, lifecycle, zip, cancel), the security layer (token, Host check,
headers), engine asset verification, and the `sweepr` CLI.

Needs deep-filter, ffmpeg and ffprobe. Point SWEEPR_BIN_DIR at a folder that
holds them, or let Sweepr download the pinned engine into the cache:

    uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from sweepr_app import __version__, assets, engine, jobs, limits  # noqa: E402
from sweepr_app.server import Settings, create_app  # noqa: E402

TOKEN = "smoke-test-token-" + hashlib.sha256(os.urandom(16)).hexdigest()[:24]
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
AUTH = {"X-Sweepr-Token": TOKEN}


def step(name: str) -> None:
    print(f"\n== {name}")


def make_wav(path: Path, sr: int, seconds: float, channels: int = 1, amplitude: float = 0.3, noise: float = 0.12) -> Path:
    """Write a 16-bit WAV: a modulated tone plus white noise (stdlib only)."""
    rng = random.Random(sr)
    frames = bytearray()
    for i in range(int(sr * seconds)):
        t = i / sr
        voice = amplitude * math.sin(2 * math.pi * 220 * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 3 * t))
        sample = voice + noise * (rng.random() * 2 - 1)
        value = max(-32768, min(32767, int(sample * 32767)))
        frames += struct.pack("<h", value) * channels
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(bytes(frames))
    return path


def wav_bytes(sr: int, seconds: float, channels: int = 1) -> bytes:
    with tempfile.TemporaryDirectory() as td:
        return make_wav(Path(td) / "a.wav", sr, seconds, channels).read_bytes()


def run_tool(tools: assets.Tools, *args: str | Path) -> str:
    proc = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    return proc.stdout + proc.stderr


def probe_streams(tools: assets.Tools, path: Path) -> list[dict]:
    proc = subprocess.run(
        [str(tools.ffprobe), "-v", "error", "-show_entries", "stream=codec_type,codec_name,sample_rate", "-of", "json", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)["streams"]


def mean_volume(tools: assets.Tools, path: Path) -> float:
    text = run_tool(tools, tools.ffmpeg, "-hide_banner", "-nostdin", "-i", path, "-af", "volumedetect", "-f", "null", "-")
    return engine._grab_db(text, "mean_volume")  # type: ignore[return-value]


def make_video(tools: assets.Tools, out: Path, *, audio: bool) -> Path:
    with tempfile.TemporaryDirectory() as td:
        cmd = [str(tools.ffmpeg), "-y", "-nostdin", "-hide_banner", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=2"]
        if audio:
            wav = make_wav(Path(td) / "in.wav", 44100, 2.0)
            cmd += ["-i", str(wav), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "mpeg4", "-c:a", "aac", "-shortest"]
        else:
            cmd += ["-c:v", "mpeg4"]
        cmd.append(str(out))
        subprocess.run(cmd, check=True, capture_output=True)
    return out


def wait_for_job(client: TestClient, job_id: str, timeout: float = 240.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}", headers=AUTH).json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.4)
    raise AssertionError(f"job {job_id} still active after {timeout}s")


def expect_reject(client: TestClient, *, files=None, data=None, why: str) -> None:
    resp = client.post(
        "/api/jobs",
        headers=AUTH,
        files=files or [("files", ("a.wav", wav_bytes(44100, 0.5), "audio/wav"))],
        data=data or {},
    )
    assert resp.status_code == 400, f"{why}: expected 400, got {resp.status_code}: {resp.text[:200]}"
    print(f"  rejected ({why}): {resp.json()['detail']['message']}")


def check_assets() -> None:
    step("engine assets")
    manifest = assets.manifest()
    assert manifest["version"] == __version__, "manifest version must match the package"
    for key in ("windows-x86_64", "macos-arm64", "macos-x86_64", "linux-x86_64"):
        entry = manifest["platforms"].get(key)
        assert entry, f"manifest missing {key}"
        pin = entry.get("deep_filter") or {}
        assert pin.get("url") and pin.get("sha256"), f"{key} has no pinned deep-filter"
        if key in ("windows-x86_64", "linux-x86_64"):
            ffmpeg = entry.get("ffmpeg") or {}
            assert ffmpeg.get("url") and ffmpeg.get("sha256"), f"{key} has no pinned ffmpeg"
    print(f"  manifest covers {len(manifest['platforms'])} platforms, version {manifest['version']}")

    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("payload.bin", b"hello")
        good = hashlib.sha256(archive.read_bytes()).hexdigest()
        dest = Path(td) / "ok.zip"
        assets._download(archive.as_uri(), dest, good, None, None)
        assert dest.read_bytes() == archive.read_bytes(), "download corrupted the archive"

        bad_dest = Path(td) / "bad.zip"
        try:
            assets._download(archive.as_uri(), bad_dest, "0" * 64, None, None)
        except assets.AssetError as exc:
            assert "checksum" in str(exc)
            assert not bad_dest.exists() and not bad_dest.with_name("bad.zip.part").exists()
            print("  checksum mismatch rejected, no partial file left behind")
        else:
            raise AssertionError("checksum mismatch was accepted")

        nested = Path(td) / "nested.zip"
        with zipfile.ZipFile(nested, "w") as zf:
            zf.writestr("../escape.exe", b"x")
        try:
            assets._extract(nested, Path(td))
        except assets.AssetError:
            assert not (Path(td).parent / "escape.exe").exists()
            print("  path-traversal archive rejected")
        else:
            raise AssertionError("traversal archive was extracted")


def check_engine(tools: assets.Tools, work: Path) -> None:
    step("engine: probe")
    info = engine.probe(make_wav(work / "p.wav", 44100, 1.0))
    assert info["sample_rate"] == 44100 and info["channels"] == 1 and not info["has_video"]
    garbage = work / "garbage.wav"
    garbage.write_bytes(b"this is definitely not audio")
    try:
        engine.probe(garbage)
    except engine.AudioError as exc:
        print(f"  garbage rejected: {exc}")
    else:
        raise AssertionError("garbage probed as audio")
    silent_video = make_video(tools, work / "silent.mp4", audio=False)
    try:
        engine.probe(silent_video)
    except engine.AudioError as exc:
        print(f"  video without audio rejected: {exc}")
    else:
        raise AssertionError("video without audio was accepted")

    step("engine: denoise keeps rate, writes 24-bit, lowers energy")
    for name, sr, channels in (("mono44k", 44100, 1), ("stereo48k", 48000, 2), ("mono22k", 22050, 1)):
        src = make_wav(work / f"{name}.wav", sr, 2.5, channels)
        dst = work / f"{name}_out.wav"
        engine.process_file(src, dst, {"atten_lim_db": 30, "post_filter": False, "normalize": False})
        stream = probe_streams(tools, dst)[0]
        assert int(stream["sample_rate"]) == sr, f"{name}: sample rate changed"
        assert stream["codec_name"] == "pcm_s24le", f"{name}: codec {stream['codec_name']}"
        before, after = mean_volume(tools, src), mean_volume(tools, dst)
        assert after < before, f"{name}: denoising did not reduce energy ({after:.1f} >= {before:.1f} dB)"
        print(f"  {name}: sr={sr} 24-bit, mean {before:.1f} -> {after:.1f} dB")

    step("engine: quiet input is lifted, loud input is left alone")
    quiet = make_wav(work / "quiet.wav", 44100, 2.0, amplitude=0.002, noise=0.001)
    loud = make_wav(work / "loud.wav", 44100, 2.0)
    assert engine._quiet_gain_db(quiet, None) > 0.0, "quiet input was not lifted"
    assert engine._quiet_gain_db(loud, None) == 0.0, "loud input was modified"
    print("  quiet lifted, loud untouched")

    step("engine: loudness normalization")
    src = make_wav(work / "norm.wav", 44100, 3.0)
    dst = work / "norm_out.wav"
    # 0 dB attenuation isolates the loudness stage: the model would otherwise
    # remove this synthetic tone, which is not speech.
    result = engine.process_file(src, dst, {"atten_lim_db": 0, "normalize": True, "target_lufs": -16.0})
    assert result["lufs_after"] is not None and abs(result["lufs_after"] + 16.0) <= 1.0, result
    print(f"  {result['lufs_before']:.1f} -> {result['lufs_after']:.1f} LUFS (target -16)")

    step("engine: video keeps picture, replaces audio")
    video = make_video(tools, work / "clip.mp4", audio=True)
    result = engine.process_file(video, work / "clip_out.wav", {"atten_lim_db": 50})
    assert result["video"] and Path(result["video"]).is_file(), result
    kinds = sorted(s["codec_type"] for s in probe_streams(tools, Path(result["video"])))
    assert kinds == ["audio", "video"], kinds
    print(f"  muxed streams: {kinds}")

    step("engine: cancel stops work")
    event = threading.Event()
    event.set()
    try:
        engine.process_file(make_wav(work / "c.wav", 44100, 2.0), work / "c_out.wav", {"atten_lim_db": 30}, event)
    except engine.Cancelled:
        print("  cancelled before any output was produced")
    else:
        raise AssertionError("cancel was ignored")


def check_api(tools: assets.Tools, data: Path) -> None:
    app = create_app(Settings(data_dir=data, token=TOKEN, port=PORT))

    step("security: token and host")
    bare = TestClient(app, base_url=BASE)  # no lifespan: pure request checks
    health = bare.get("/api/health")
    assert health.status_code == 200 and health.json()["version"] == __version__
    assert health.headers["content-security-policy"].startswith("default-src 'self'")
    assert health.headers["referrer-policy"] == "no-referrer"
    assert bare.get("/api/jobs").status_code == 401, "missing token must be rejected"
    assert bare.get("/api/jobs", headers={"X-Sweepr-Token": "wrong"}).status_code == 401
    evil = TestClient(app, base_url="http://attacker.example")
    assert evil.get("/api/health").status_code == 400, "foreign Host must be rejected"
    rebind = TestClient(app, base_url=f"http://127.0.0.1:{PORT + 1}")
    assert rebind.get("/api/health").status_code == 400, "wrong port in Host must be rejected"
    print("  401 without/with wrong token, 400 for foreign Host, health stays public")

    step("security: empty token refused")
    for bad in ("", "   "):
        try:
            Settings(data_dir=data, token=bad)
        except ValueError:
            continue
        raise AssertionError(f"empty token accepted: {bad!r}")
    print("  empty tokens rejected at startup")

    with TestClient(app, base_url=BASE) as client:
        step("jobs: batch denoise, downloads, zip, delete")
        clips = [
            ("podcast_take1.wav", wav_bytes(44100, 3.0, 1)),
            ("demo_stereo.wav", wav_bytes(48000, 2.0, 2)),
            ("meeting_22k.wav", wav_bytes(22050, 2.5, 1)),
        ]
        resp = client.post(
            "/api/jobs",
            headers=AUTH,
            files=[("files", (name, data_bytes, "audio/wav")) for name, data_bytes in clips],
            data={"atten_lim_db": "100", "post_filter": "false"},
        )
        assert resp.status_code == 202, resp.text
        job_id = resp.json()["job_id"]
        job = wait_for_job(client, job_id)
        assert job["status"] == "done", [f.get("error") for f in job["files"]]

        for i, (name, original) in enumerate(clips):
            result = client.get(f"/api/jobs/{job_id}/files/{i}", params={"which": "out", "token": TOKEN})
            assert result.status_code == 200, f"{name}: query-token download failed ({result.status_code})"
            assert result.content[:4] == b"RIFF", f"{name}: not a WAV"
            print(f"  {name}: enhanced WAV downloaded via query token ({len(result.content)} bytes)")

        zip_resp = client.get(f"/api/jobs/{job_id}/zip", headers=AUTH)
        assert zip_resp.status_code == 200 and zip_resp.content[:2] == b"PK"
        assert len(zipfile.ZipFile(io.BytesIO(zip_resp.content)).namelist()) == 3
        print("  zip OK")
        assert client.delete(f"/api/jobs/{job_id}", headers=AUTH).status_code == 204

        step("jobs: validation")
        expect_reject(client, files=[("files", ("fake.wav", b"not audio", "audio/wav"))], why="garbage bytes")
        expect_reject(client, files=[("files", ("notes.txt", b"hello", "text/plain"))], why="disallowed type")
        expect_reject(
            client,
            files=[("files", (f"x{i}.wav", wav_bytes(44100, 0.2), "audio/wav")) for i in range(11)],
            why="11 files",
        )
        expect_reject(client, data={"atten_lim_db": "200"}, why="attenuation out of range")
        expect_reject(client, data={"normalize": "true", "target_lufs": "0"}, why="loudness out of range")
        expect_reject(
            client,
            files=[("files", ("silent.mp4", make_video(tools, data / "silent-up.mp4", audio=False).read_bytes(), "video/mp4"))],
            why="video without audio",
        )
        assert client.get("/api/jobs/not-a-uuid", headers=AUTH).status_code == 404
        assert client.get("/api/jobs/..%2F..%2Fetc", headers=AUTH).status_code in (404, 422)
        print("  invalid ids -> 404/422")

        step("jobs: video end to end")
        video = make_video(tools, data / "clip.mp4", audio=True)
        resp = client.post(
            "/api/jobs",
            headers=AUTH,
            files=[("files", ("clip.mp4", video.read_bytes(), "video/mp4"))],
            data={"atten_lim_db": "50"},
        )
        assert resp.status_code == 202, resp.text
        vid = wait_for_job(client, resp.json()["job_id"])
        assert vid["status"] == "done", [f.get("error") for f in vid["files"]]
        muxed = client.get(f"/api/jobs/{vid['id']}/files/0", params={"which": "video", "token": TOKEN})
        assert muxed.status_code == 200, muxed.status_code
        print(f"  video job OK, muxed download {len(muxed.content)} bytes")
        client.delete(f"/api/jobs/{vid['id']}", headers=AUTH)

        step("jobs: cancel a running job")
        long_clip = wav_bytes(44100, 40.0)
        resp = client.post("/api/jobs", headers=AUTH, files=[("files", ("long.wav", long_clip, "audio/wav"))], data={})
        assert resp.status_code == 202, resp.text
        long_id = resp.json()["job_id"]
        time.sleep(0.5)
        deleted = client.delete(f"/api/jobs/{long_id}", headers=AUTH)
        assert deleted.status_code in (202, 204), deleted.status_code
        deadline = time.time() + 120
        while time.time() < deadline and jobs.job_dir(long_id).exists():
            time.sleep(0.3)
        assert not jobs.job_dir(long_id).exists(), "cancelled job was not purged"
        print("  cancelled job purged, worker idle")


def check_cli(tools: assets.Tools, data: Path) -> None:
    step("cli")
    env = {
        **os.environ,
        "SWEEPR_DATA_DIR": str(data / "cli-data"),
        "SWEEPR_CACHE_DIR": str(data / "cli-cache"),
        "SWEEPR_BIN_DIR": str(tools.deep_filter.parent),
    }
    version = subprocess.run([sys.executable, "-m", "sweepr_app", "--version"], capture_output=True, text=True, env=env, cwd=ROOT)
    assert version.returncode == 0 and __version__ in version.stdout, version.stdout + version.stderr
    print(f"  {version.stdout.strip()}")
    doctor = subprocess.run([sys.executable, "-m", "sweepr_app", "doctor"], capture_output=True, text=True, env=env, cwd=ROOT)
    assert doctor.returncode == 0, doctor.stdout + doctor.stderr
    assert "deep-filter" in doctor.stdout and "ffmpeg" in doctor.stdout
    print("  doctor: all checks passed")


def main() -> None:
    if os.environ.get("SWEEPR_BIN_DIR") is None and not assets.is_ready():
        print("Engine not found. Downloading the pinned engine into the cache...")
        assets.ensure_tools()
    tools = assets.resolve_tools()
    print(f"engine: {tools.deep_filter}")
    print(f"ffmpeg: {shutil.which('ffmpeg') or tools.ffmpeg}")

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == __version__, "pyproject and package version differ"
    assert pyproject["project"]["name"] == "sweepr-app"
    assert pyproject["project"]["scripts"]["sweepr"] == "sweepr_app.cli:main"
    print(f"sweepr {__version__} ({limits.MAX_FILES} files, {limits.MAX_FILE_BYTES // 1024**3} GB per file)")

    check_assets()
    with tempfile.TemporaryDirectory(prefix="sweepr-smoke-") as tmp:
        work = Path(tmp)
        check_engine(tools, work)
        check_api(tools, work)
        check_cli(tools, work)
    print("\nOK")


if __name__ == "__main__":
    main()
