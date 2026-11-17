"""Build the pinned deep-filter CLI (DeepFilterNet3) from source.

The release pipeline runs this on each platform runner. The result is a single
`deep-filter` executable with the DeepFilterNet3 model compiled in.

    uv run python scripts/build_engine.py --out dist/engine

Pins are recorded here so a release can always be rebuilt bit-for-bit from the
same inputs. Bump them deliberately, together, and note it in the CHANGELOG.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEEPFILTERNET_REPO = "https://github.com/Rikorose/DeepFilterNet.git"
DEEPFILTERNET_TAG = "v0.5.6"
DEEPFILTERNET_COMMIT = "978576aa8400552a4ce9730838c635aa30db5e61"
# Upstream's Cargo.lock pins time 0.3.28, which current rustc rejects (E0282).
# This is the minimal bump that compiles; it does not change DSP code.
TIME_CRATE_PIN = ("time", "0.3.36")
FEATURES = "bin,tract,wav-utils,transforms,default-model"


def run(cmd: list[str | Path], cwd: Path | None = None) -> str:
    proc = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit(f"command failed: {' '.join(str(c) for c in cmd)}")
    return proc.stdout.strip()


def checkout(workdir: Path) -> Path:
    src = workdir / "DeepFilterNet"
    if not (src / ".git").is_dir():
        workdir.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--branch", DEEPFILTERNET_TAG, DEEPFILTERNET_REPO, src])
    head = run(["git", "rev-parse", "HEAD"], cwd=src)
    if head != DEEPFILTERNET_COMMIT:
        raise SystemExit(f"expected {DEEPFILTERNET_TAG} at {DEEPFILTERNET_COMMIT}, found {head}")
    return src


def build(src: Path) -> Path:
    name, version = TIME_CRATE_PIN
    run(["cargo", "update", "-p", name, "--precise", version], cwd=src)
    run(
        [
            "cargo",
            "build",
            "--release",
            "-p",
            "deep_filter",
            "--features",
            FEATURES,
            "--bin",
            "deep-filter",
        ],
        cwd=src,
    )
    exe = "deep-filter.exe" if sys.platform == "win32" else "deep-filter"
    return src / "target" / "release" / exe


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", type=Path, default=ROOT / "build" / "engine", help="source checkout location")
    parser.add_argument("--out", type=Path, default=ROOT / "dist" / "engine", help="where to place the binary")
    args = parser.parse_args()

    src = checkout(args.workdir.resolve())
    built = build(src)
    version = run([built, "--version"])
    if DEEPFILTERNET_TAG.lstrip("v") not in version:
        raise SystemExit(f"unexpected version output: {version!r}")

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / built.name
    shutil.copy2(built, dest)
    shutil.copy2(src / "LICENSE-MIT", args.out / "LICENSE-deep-filter-MIT.txt")
    shutil.copy2(src / "LICENSE-APACHE", args.out / "LICENSE-deep-filter-APACHE.txt")
    print(f"built {dest} ({version})")


if __name__ == "__main__":
    main()
