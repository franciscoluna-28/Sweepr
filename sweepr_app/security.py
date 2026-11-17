"""Request guard for the local server.

Sweepr listens on loopback, but any web page or local process can still reach
it. Three checks make that safe:

* Host allowlist: a page on another site cannot reach us via DNS rebinding,
  because the browser sends that site's host name.
* Access token: every /api route except /api/health needs the per-launch token,
  in the X-Sweepr-Token header or, for GET requests only, a ``token`` query
  parameter (needed because <audio> and <a download> cannot set headers).
* Security headers: a strict Content-Security-Policy and no referrer leakage,
  so the token in media URLs never reaches a third party.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from urllib.parse import parse_qs

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PUBLIC_PATHS = frozenset({"/api/health"})

SECURITY_HEADERS = (
    (
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    ),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("X-Frame-Options", "DENY"),
)


def allowed_hosts(port: int, extra: Iterable[str] = ()) -> frozenset[str]:
    base = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    return frozenset(base | {h.strip().lower() for h in extra if h.strip()})


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, *, token: str, hosts: frozenset[str]) -> None:
        self.app = app
        self.token = token
        self.hosts = hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        if headers.get("host", "").lower() not in self.hosts:
            await self._reject(scope, receive, send, 400, "invalid host header")
            return

        path = scope["path"]
        if path.startswith("/api/") and path not in PUBLIC_PATHS and not self._authorized(scope, headers):
            await self._reject(scope, receive, send, 401, "missing or invalid access token")
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS:
                    response_headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _authorized(self, scope: Scope, headers: dict[str, str]) -> bool:
        presented = headers.get("x-sweepr-token")
        if presented is None and scope["method"] == "GET":
            query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
            presented = (query.get("token") or [None])[0]
        if presented is None:
            return False
        return secrets.compare_digest(presented.encode("utf-8"), self.token.encode("utf-8"))

    async def _reject(self, scope: Scope, receive: Receive, send: Send, status: int, message: str) -> None:
        body = {"detail": {"message": message, "errors": [message]}}
        response = JSONResponse(body, status_code=status)
        await response(scope, receive, send)
