import argparse
import asyncio
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).parents[1] / "mcp-servers" / "sse_security.py"
SPEC = importlib.util.spec_from_file_location("sse_security", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
security = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(security)

TOKEN = "x" * 32


async def status_for(app, authorization=None):
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    messages = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    await app(
        {"type": "http", "method": "GET", "path": "/sse", "headers": headers},
        receive,
        send,
    )
    return messages[0]["status"]


class SSESecurityTest(unittest.TestCase):
    def test_sse_defaults_to_loopback(self):
        parser = argparse.ArgumentParser()
        security.add_sse_arguments(parser, 8000)
        args = parser.parse_args(["--transport", "sse"])
        self.assertEqual(args.host, "127.0.0.1")

    def test_remote_bind_requires_token(self):
        server = Mock()
        with patch.dict(security.os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MCP_AUTH_TOKEN"):
                security.run_sse(server, "0.0.0.0", 8000)

    def test_short_token_is_rejected(self):
        with patch.dict(security.os.environ, {"MCP_AUTH_TOKEN": "short"}):
            with self.assertRaisesRegex(RuntimeError, "32"):
                security.run_sse(Mock(), "127.0.0.1", 8000)

    def test_non_ascii_token_is_rejected_at_startup(self):
        with patch.dict(security.os.environ, {"MCP_AUTH_TOKEN": "密" * 32}):
            with self.assertRaisesRegex(RuntimeError, "ASCII"):
                security.run_sse(Mock(), "127.0.0.1", 8000)

    def test_non_http_scopes_bypass_bearer_auth(self):
        seen = []

        async def downstream(scope, receive, send):
            seen.append(scope["type"])

        app = security.BearerAuthMiddleware(downstream, TOKEN)
        asyncio.run(app({"type": "lifespan"}, None, None))
        self.assertEqual(seen, ["lifespan"])

    def test_bearer_token_is_required_when_configured(self):
        async def downstream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        app = security.BearerAuthMiddleware(downstream, TOKEN)
        self.assertEqual(asyncio.run(status_for(app)), 401)
        self.assertEqual(asyncio.run(status_for(app, "Bearer wrong")), 401)
        self.assertEqual(asyncio.run(status_for(app, f"Bearer {TOKEN}")), 200)


if __name__ == "__main__":
    unittest.main()
