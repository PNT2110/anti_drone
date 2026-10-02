"""Optional password gate for the web console.

Set ANTI_DRONE_PASSWORD to require HTTP Basic credentials (any user name).
A successful Basic login also sets a session cookie, because browsers do not
reliably resend the Authorization header on WebSocket handshakes.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import ipaddress
import os
import secrets
from http.cookies import SimpleCookie

SESSION_COOKIE = "anti_drone_session"
# Regenerated on every start, so old cookies stop working after a restart.
_SESSION_SECRET = secrets.token_bytes(32)


def get_password() -> str | None:
    return os.getenv("ANTI_DRONE_PASSWORD") or None


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def session_token(password: str) -> str:
    return hmac.new(_SESSION_SECRET, password.encode("utf-8"), hashlib.sha256).hexdigest()


def _basic_ok(header: bytes | None, password: str) -> bool:
    if not header:
        return False
    scheme, _, encoded = header.decode("latin-1").partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    _, separator, supplied = decoded.partition(":")
    if not separator:
        return False
    return hmac.compare_digest(supplied.encode("utf-8"), password.encode("utf-8"))


def _cookie_ok(header: bytes | None, password: str) -> bool:
    if not header:
        return False
    cookie = SimpleCookie()
    try:
        cookie.load(header.decode("latin-1"))
    except Exception:
        return False
    morsel = cookie.get(SESSION_COOKIE)
    if morsel is None:
        return False
    return hmac.compare_digest(morsel.value, session_token(password))


class BasicAuthMiddleware:
    """Pure ASGI middleware so the same check covers HTTP and WebSocket."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        password = get_password()
        if scope["type"] not in ("http", "websocket") or password is None:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        via_cookie = _cookie_ok(headers.get(b"cookie"), password)
        via_basic = _basic_ok(headers.get(b"authorization"), password)

        if not (via_cookie or via_basic):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            body = "Cần đăng nhập.".encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b'Basic realm="anti-drone", charset="UTF-8"'),
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        if scope["type"] == "http" and not via_cookie:
            set_cookie = (
                f"{SESSION_COOKIE}={session_token(password)}; Path=/; HttpOnly; SameSite=Strict"
            ).encode("ascii")

            async def send_with_cookie(message) -> None:
                if message["type"] == "http.response.start":
                    message = dict(message)
                    message["headers"] = list(message.get("headers") or []) + [
                        (b"set-cookie", set_cookie)
                    ]
                await send(message)

            await self.app(scope, receive, send_with_cookie)
            return

        await self.app(scope, receive, send)
