"""The `sweepr` command: start the local app, check the install, or pre-seed the engine."""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import socket
import sys
import threading
import webbrowser

from . import __version__, assets, paths


def _progress(done: int, total: int | None) -> None:
    if total:
        sys.stderr.write(f"\r  downloading engine... {done * 100 // total:3d}%")
    else:
        sys.stderr.write(f"\r  downloading engine... {done // (1024 * 1024)} MB")
    sys.stderr.flush()
    if total and done >= total:
        sys.stderr.write("\n")


def _url(port: int, token: str | None = None, host: str = "127.0.0.1") -> str:
    base = f"http://{host}:{port}/"
    return f"{base}#token={token}" if token else base


def _pick_port(host: str) -> int:
    for candidate in (paths.DEFAULT_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, candidate))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise OSError("no free port available on this machine")


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def serve(args: argparse.Namespace) -> int:
    data = paths.data_dir(args.data_dir)
    print(f"Sweepr {__version__}")
    try:
        assets.ensure_tools(progress=_progress)
    except assets.AssetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    host = args.host
    token = args.token or secrets.token_urlsafe(32)
    port = args.port or _pick_port(host)
    trusted = list(args.trusted_host) + [
        h for h in os.environ.get("SWEEPR_TRUSTED_HOSTS", "").split(",") if h.strip()
    ]
    remote = host not in ("127.0.0.1", "localhost", "::1")
    if remote:
        print(
            f"warning: listening on {host}. Anyone who can reach this port needs the token. "
            "Put a TLS reverse proxy in front of it.",
            file=sys.stderr,
        )
        if not trusted:
            print(
                "warning: SWEEPR_TRUSTED_HOSTS is empty, so remote browsers will be rejected "
                "with 'invalid host header'. Add the exact host:port you use to open Sweepr.",
                file=sys.stderr,
            )

    import uvicorn

    from .server import Settings, create_app

    settings = Settings(data_dir=data, token=token, port=port, trusted_hosts=tuple(trusted))
    app = create_app(settings)

    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") or not remote else host
    url = _url(port, token, display_host)
    print(f"Sweepr is running at {_url(port)}")
    print("Open it with this link (keep this window open; Ctrl+C stops Sweepr):")
    print(f"  {url}")
    if remote:
        target = display_host if display_host != "127.0.0.1" else "<server-address>"
        print(f"From another machine: http://{target}:{port}/#token={token}")
        print("Use the published host port if it differs from the port above.")
        if not trusted:
            print(
                f"Add the exact host:port you open ({target}:{port}, or the published port) "
                "to SWEEPR_TRUSTED_HOSTS."
            )
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    config = uvicorn.Config(app, host=host, port=port, log_level="warning", access_log=False)
    uvicorn.Server(config).run()
    return 0


def doctor() -> int:
    ok = True

    def line(status: str, label: str, detail: str = "") -> None:
        nonlocal ok
        if status == "FAIL":
            ok = False
        print(f"  [{status:4}] {label}{': ' + detail if detail else ''}")

    print(f"Sweepr {__version__}")
    print(f"  python    {sys.version.split()[0]} on {sys.platform}")
    try:
        key = assets.platform_key()
        line("OK", "platform", key)
    except assets.AssetError as exc:
        line("FAIL", "platform", str(exc))
        return 1

    for label, directory in (("data dir", paths.data_dir()), ("cache dir", paths.cache_dir())):
        try:
            probe = directory / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            line("OK", label, str(directory))
        except OSError as exc:
            line("FAIL", label, f"{directory} is not writable ({exc})")

    try:
        tools = assets.resolve_tools()
        for name, tool in (("deep-filter", tools.deep_filter), ("ffmpeg", tools.ffmpeg), ("ffprobe", tools.ffprobe)):
            line("OK", name, f"{tool.name}  ({assets.tool_version(tool)})")
    except assets.AssetError as exc:
        line("FAIL", "engine", str(exc))

    port = paths.DEFAULT_PORT
    if _port_free(port):
        line("OK", "port", f"{port} is free")
    else:
        line("OK", "port", f"{port} is in use; Sweepr will pick another port")

    print("OK" if ok else "Some checks failed. See the messages above.")
    return 0 if ok else 1


def install_assets() -> int:
    try:
        tools = assets.ensure_tools(progress=_progress)
    except assets.AssetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"engine ready: {tools.deep_filter.parent}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sweepr",
        description="Remove background noise from audio and video, locally, in your browser.",
    )
    parser.add_argument("--version", action="version", version=f"sweepr {__version__}")
    parser.add_argument("--host", default="127.0.0.1", help="interface to listen on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, help="port to listen on (default: 8765, or a free port)")
    parser.add_argument("--data-dir", help="where jobs and logs are stored")
    parser.add_argument("--token", default=os.environ.get("SWEEPR_TOKEN"), help="fixed access token (default: random)")
    parser.add_argument(
        "--trusted-host",
        action="append",
        default=[],
        metavar="HOST[:PORT]",
        help="extra Host header to accept, e.g. for a reverse proxy (repeatable)",
    )
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    parser.add_argument("-v", "--verbose", action="store_true", help="show server log messages")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor", help="check the install and print what is missing")
    sub.add_parser("install-assets", help="download the engine now (used when building images)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if args.command == "doctor":
        return doctor()
    if args.command == "install-assets":
        return install_assets()
    if args.port is not None and not 1 <= args.port <= 65535:
        print("error: --port must be between 1 and 65535", file=sys.stderr)
        return 2
    try:
        return serve(args)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
