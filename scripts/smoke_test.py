"""End-to-end smoke test for the batch job API.

Builds synthetic noisy clips, drives the real FastAPI app through TestClient
(the lifespan warms the models and starts the worker thread), and asserts the
full pipeline: validation, denoising, sample-rate preservation, zip, delete.

Run from the project root:

    .venv\\Scripts\\python.exe scripts\\smoke_test.py
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app


def make_wav(sr: int, duration: float, channels: int) -> bytes:
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    rng = np.random.default_rng(int(sr))
    voice = 0.3 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    noise = 0.12 * rng.standard_normal(t.shape)
    mono = (voice + noise).astype(np.float32)
    data = np.stack([mono] * channels, axis=1) if channels > 1 else mono
    buf = io.BytesIO()
    sf.write(buf, data, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def make_video(*, audio: bool = True) -> bytes:
    """Render a tiny mp4 (with or without an audio track) via ffmpeg."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "clip.mp4")
        cmd = ["ffmpeg", "-y", "-nostdin"]
        if audio:
            wav = os.path.join(td, "in.wav")
            with open(wav, "wb") as f:
                f.write(make_wav(44100, 2.0, 1))
            cmd += [
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=64x64:d=2",
                "-i",
                wav,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "mpeg4",
                "-c:a",
                "aac",
                "-shortest",
                out,
            ]
        else:
            cmd += [
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=64x64:d=1",
                "-c:v",
                "mpeg4",
                out,
            ]
        subprocess.run(cmd, check=True, capture_output=True)
        with open(out, "rb") as f:
            return f.read()


def wait_for_job(client, job_id: str, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.5)
    raise AssertionError(f"job {job_id} still {job['status']} after {timeout}s")


def expect_reject(client, *, files=None, data=None, why: str = "") -> None:
    resp = client.post(
        "/api/jobs",
        files=files or [("files", ("a.wav", make_wav(44100, 0.5, 1), "audio/wav"))],
        data=data or {},
    )
    assert resp.status_code == 400, (
        f"{why}: expected 400, got {resp.status_code}: {resp.text[:300]}"
    )
    detail = resp.json()["detail"]
    assert isinstance(detail, dict) and detail.get("errors"), (
        f"{why}: no errors list: {detail}"
    )
    print(f"  rejected as expected ({why}): {detail['message']}")


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        limits = health["limits"]
        assert limits["max_files"] == 10 and limits["max_file_mb"] == 5120
        print("health OK, limits:", limits)

        clips = [
            ("podcast_take1.wav", make_wav(44100, 3.0, 1)),
            ("demo_stereo.wav", make_wav(48000, 2.0, 2)),
            ("meeting_22k.wav", make_wav(22050, 2.5, 1)),
        ]
        resp = client.post(
            "/api/jobs",
            files=[("files", (name, data, "audio/wav")) for name, data in clips],
            data={"atten_lim_db": "100", "post_filter": "false"},
        )
        assert resp.status_code == 202, f"create failed: {resp.status_code} {resp.text}"
        job_id = resp.json()["job_id"]
        print(f"job {job_id} accepted")

        job = wait_for_job(client, job_id)
        assert job["status"] == "done", (
            f"job status {job['status']}: {[f.get('error') for f in job['files']]}"
        )
        print(f"job done in poll loop, status={job['status']}")

        for i, (name, original) in enumerate(clips):
            entry = job["files"][i]
            assert entry["status"] == "done", entry
            src_sr = sf.info(io.BytesIO(original)).samplerate
            result = client.get(
                f"/api/jobs/{job_id}/files/{i}", params={"which": "out"}
            )
            assert result.status_code == 200, result.status_code
            out, out_sr = sf.read(io.BytesIO(result.content))
            info = sf.info(io.BytesIO(result.content))
            assert out_sr == src_sr, f"{name}: sample rate {out_sr} != {src_sr}"
            assert info.subtype == "PCM_24", f"{name}: subtype {info.subtype}"
            orig, _ = sf.read(io.BytesIO(original))
            in_rms = float(np.sqrt((orig.astype(np.float64) ** 2).mean()))
            out_rms = float(np.sqrt((out.astype(np.float64) ** 2).mean()))
            assert out_rms < in_rms, (
                f"{name}: denoising did not reduce energy ({out_rms:.5f} >= {in_rms:.5f})"
            )
            print(
                f"  {name}: sr={out_sr} preserved, 24-bit, rms {in_rms:.4f} -> {out_rms:.4f}"
            )

            original_resp = client.get(
                f"/api/jobs/{job_id}/files/{i}", params={"which": "in"}
            )
            assert original_resp.status_code == 200

        zip_resp = client.get(f"/api/jobs/{job_id}/zip")
        assert zip_resp.status_code == 200 and zip_resp.content[:2] == b"PK", (
            "zip download failed"
        )
        import zipfile as zf

        names = zf.ZipFile(io.BytesIO(zip_resp.content)).namelist()
        assert len(names) == 3, names
        print(f"zip OK: {names}")

        # Single file is just a 1-file job — same path.
        resp = client.post(
            "/api/jobs",
            files=[("files", ("single.wav", make_wav(44100, 1.5, 1), "audio/wav"))],
            data={"atten_lim_db": "50"},
        )
        assert resp.status_code == 202
        single = wait_for_job(client, resp.json()["job_id"])
        assert single["status"] == "done", single
        print("single-file job OK")
        client.delete(f"/api/jobs/{single['id']}")

        if shutil.which("ffmpeg"):
            resp = client.post(
                "/api/jobs",
                files=[
                    (
                        "files",
                        ("normalize_me.wav", make_wav(44100, 3.0, 1), "audio/wav"),
                    )
                ],
                data={"atten_lim_db": "50", "normalize": "true", "target_lufs": "-16"},
            )
            assert resp.status_code == 202, resp.text
            norm = wait_for_job(client, resp.json()["job_id"])
            assert norm["status"] == "done", [f.get("error") for f in norm["files"]]
            entry = norm["files"][0]
            assert entry["lufs_before"] is not None, entry
            assert entry["lufs_after"] is not None, entry
            assert abs(entry["lufs_after"] - (-16.0)) <= 1.0, entry
            out = client.get(f"/api/jobs/{norm['id']}/files/0", params={"which": "out"})
            assert out.status_code == 200
            print(
                f"normalize OK: {entry['lufs_before']:.1f} -> "
                f"{entry['lufs_after']:.1f} LUFS (target -16)"
            )
            client.delete(f"/api/jobs/{norm['id']}")
        else:
            print("skipping normalize job: ffmpeg not on PATH")

        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            resp = client.post(
                "/api/jobs",
                files=[("files", ("clip.mp4", make_video(), "video/mp4"))],
                data={"atten_lim_db": "50"},
            )
            assert resp.status_code == 202, resp.text
            vid = wait_for_job(client, resp.json()["job_id"])
            assert vid["status"] == "done", [f.get("error") for f in vid["files"]]
            result = client.get(
                f"/api/jobs/{vid['id']}/files/0", params={"which": "out"}
            )
            assert result.status_code == 200
            info = sf.info(io.BytesIO(result.content))
            assert info.samplerate == 44100 and info.subtype == "PCM_24", info
            print(f"video job OK: cleaned audio sr={info.samplerate}, {info.subtype}")

            entry = vid["files"][0]
            assert entry.get("video"), entry
            muxed = client.get(
                f"/api/jobs/{vid['id']}/files/0", params={"which": "video"}
            )
            assert muxed.status_code == 200, muxed.status_code
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
                tf.write(muxed.content)
                muxed_path = tf.name
            try:
                probe = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "stream=codec_type",
                        "-of",
                        "json",
                        muxed_path,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            finally:
                os.remove(muxed_path)
            kinds = [s["codec_type"] for s in json.loads(probe.stdout)["streams"]]
            assert kinds.count("video") == 1 and kinds.count("audio") == 1, kinds
            print(f"video output OK: muxed streams={kinds}")

            vid_zip = client.get(f"/api/jobs/{vid['id']}/zip")
            assert vid_zip.status_code == 200
            vid_names = zf.ZipFile(io.BytesIO(vid_zip.content)).namelist()
            assert (
                "clip_enhanced.wav" in vid_names and "clip_enhanced.mp4" in vid_names
            ), vid_names
            print(f"video zip OK: {vid_names}")
            client.delete(f"/api/jobs/{vid['id']}")
        else:
            print("skipping video job: ffmpeg/ffprobe not on PATH")

        print("validation checks:")
        expect_reject(
            client,
            files=[
                ("files", ("fake.wav", b"this is definitely not audio", "audio/wav"))
            ],
            why="garbage bytes as .wav",
        )
        expect_reject(
            client,
            files=[("files", ("notes.txt", b"hello", "text/plain"))],
            why="disallowed extension",
        )
        expect_reject(
            client,
            files=[
                ("files", (f"x{i}.wav", make_wav(44100, 0.2, 1), "audio/wav"))
                for i in range(11)
            ],
            why="11 files",
        )
        expect_reject(client, data={"atten_lim_db": "200"}, why="atten out of range")
        expect_reject(
            client,
            data={"normalize": "true", "target_lufs": "0"},
            why="target_lufs out of range",
        )

        if shutil.which("ffmpeg") and shutil.which("ffprobe"):
            expect_reject(
                client,
                files=[("files", ("silent.mp4", make_video(audio=False), "video/mp4"))],
                why="video with no audio track",
            )

        assert client.get("/api/jobs/not-a-uuid").status_code == 404
        assert (
            client.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code
            == 404
        )
        print("  job-id traversal/unknown ids -> 404")

        resp = client.delete(f"/api/jobs/{job_id}")
        assert resp.status_code == 204, resp.status_code
        assert client.get(f"/api/jobs/{job_id}").status_code == 404
        print("delete OK, job dir gone")

    print("OK")


if __name__ == "__main__":
    main()
