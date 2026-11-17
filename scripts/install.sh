#!/usr/bin/env sh
# Install and start Sweepr on macOS or Linux.
#
#   curl -fsSL https://github.com/franciscoluna-28/sweepr/releases/latest/download/install.sh | sh
#
# Downloads a pinned copy of uv (checksum verified) if you do not already have
# one, then runs `uvx --from sweepr-app==<version> sweepr`. Nothing is installed
# system-wide and no shell profile is changed. Arguments after the script are
# passed to `sweepr` (for example: --no-browser --port 9000).
set -eu

VERSION="${SWEEPR_VERSION:-1.0.0}"
UV_VERSION="0.13.8"
BOOT="${XDG_DATA_HOME:-$HOME/.local/share}/sweepr/bootstrap"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  TRIPLE="aarch64-apple-darwin";      SHA="6b71028a6b904f2ae3340ef52e595512de807d06c0a20eaef2f692581b246558" ;;
  Darwin-x86_64) TRIPLE="x86_64-apple-darwin";       SHA="a04c2ffeac28b2003a2c13caf538ab425fcd7def3e4a41571f4a8fb370a66af3" ;;
  Linux-x86_64)  TRIPLE="x86_64-unknown-linux-gnu";  SHA="5acfd9177cfecf0bf87578f059728215ccc884388988f55f7a65041b57387d91" ;;
  *)
    echo "error: Sweepr does not support $(uname -s) $(uname -m) yet." >&2
    exit 1
    ;;
esac

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

if command -v uvx >/dev/null 2>&1; then
  UVX="$(command -v uvx)"
else
  UVX="$BOOT/uv/uvx"
  if [ ! -x "$UVX" ]; then
    echo "==> Downloading uv $UV_VERSION (checksum verified)"
    mkdir -p "$BOOT/uv"
    tmp="$(mktemp -d)"
    curl -fsSL "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$TRIPLE.tar.gz" -o "$tmp/uv.tar.gz"
    actual="$(sha256_of "$tmp/uv.tar.gz")"
    if [ "$actual" != "$SHA" ]; then
      echo "error: uv checksum mismatch (expected $SHA, got $actual). Nothing was installed." >&2
      exit 1
    fi
    tar -xzf "$tmp/uv.tar.gz" -C "$tmp"
    mv "$tmp/uv-$TRIPLE/uv" "$tmp/uv-$TRIPLE/uvx" "$BOOT/uv/"
    rm -rf "$tmp"
  fi
fi

echo "==> Starting Sweepr $VERSION (the first run downloads the engine, about 100 MB)"
exec "$UVX" --from "sweepr-app==$VERSION" sweepr "$@"
