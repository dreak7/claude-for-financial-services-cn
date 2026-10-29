"""Shared, fail-closed SSE transport security for the local MCP servers."""

import argparse
import hmac
import ipaddress
import os


def add_sse_arguments(parser: argparse.ArgumentParser, default_port: int) -> None:
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=default_port)
    parser.add_argument("--host", default="127.0.0.1")


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class BearerAuthMiddleware:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        expected = f"Bearer {self.token}"
        if not hmac.compare_digest(authorization, expected):
            body = b"Unauthorized"
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b"Bearer"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def run_sse(server, host: str, port: int) -> None:
    token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    if token and (len(token) < 32 or not token.isascii()):
        raise RuntimeError("MCP_AUTH_TOKEN must be ASCII and contain at least 32 characters")
    if not _is_loopback(host) and not token:
        raise RuntimeError("Non-loopback SSE binding requires MCP_AUTH_TOKEN (32+ characters)")

    app = server.sse_app()
    if token:
        app = BearerAuthMiddleware(app, token)

    import uvicorn
    uvicorn.run(app, host=host, port=port)
