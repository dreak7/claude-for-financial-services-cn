import importlib.util
import ssl
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class FastMCPStub:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        return lambda function: function


mcp = types.ModuleType("mcp")
mcp.FastMCP = FastMCPStub
sys.modules["mcp"] = mcp

SERVER_PATH = Path(__file__).parents[1] / "mcp-servers" / "ifind-mcp" / "server.py"
SPEC = importlib.util.spec_from_file_location("ifind_server", SERVER_PATH)
assert SPEC is not None and SPEC.loader is not None
ifind = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ifind)


class IfindTLSTest(unittest.TestCase):
    def test_post_verifies_server_certificate(self):
        response = Mock(text="")
        with patch.object(ifind._session, "post", return_value=response) as post:
            ifind._post("stock", {"jsonrpc": "2.0"})
        self.assertIs(post.call_args.kwargs["verify"], True)

    def test_initialization_notification_verifies_server_certificate(self):
        response = Mock(headers={"Mcp-Session-Id": "session"})
        with (
            patch.object(ifind, "_post", return_value=(response, {})),
            patch.object(ifind._session, "post") as post,
        ):
            ifind._init_session("stock")
        self.assertIs(post.call_args.kwargs["verify"], True)

    def test_ssl_adapter_verifies_hostname_and_requires_tls_1_2(self):
        context = ifind.CompatibleSSLAdapter().poolmanager.connection_pool_kw["ssl_context"]
        self.assertIs(context.check_hostname, True)
        self.assertEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)


if __name__ == "__main__":
    unittest.main()
