import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


anthropic = types.ModuleType("anthropic")
anthropic.Anthropic = Mock
sys.modules["anthropic"] = anthropic

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "orchestrate.py"
SPEC = importlib.util.spec_from_file_location("orchestrate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
orchestrate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(orchestrate)

HANDOFF_TEXT = json.dumps({
    "type": "handoff_request",
    "target_agent": "china-model-builder",
    "payload": {"event": "Build DCF"},
})


class Stream:
    def __enter__(self):
        return iter([SimpleNamespace(type="message_delta", text=HANDOFF_TEXT)])

    def __exit__(self, *args):
        pass


class HandoffAuthorizationTest(unittest.TestCase):
    def make_client(self):
        client = Mock()
        client.beta.agents.sessions.stream.return_value = Stream()
        return client

    def test_denied_handoff_is_not_steered(self):
        client = self.make_client()
        with (
            patch.object(orchestrate.anthropic, "Anthropic", return_value=client),
            patch("builtins.input", return_value="no"),
        ):
            orchestrate.run("source", {"china-model-builder": "target"})
        client.beta.agents.sessions.steer.assert_not_called()

    def test_noninteractive_handoff_fails_closed(self):
        client = self.make_client()
        with (
            patch.object(orchestrate.anthropic, "Anthropic", return_value=client),
            patch("builtins.input", side_effect=EOFError),
        ):
            orchestrate.run("source", {"china-model-builder": "target"})
        client.beta.agents.sessions.steer.assert_not_called()

    def test_explicit_yes_allows_handoff(self):
        client = self.make_client()
        with (
            patch.object(orchestrate.anthropic, "Anthropic", return_value=client),
            patch("builtins.input", return_value="yes"),
        ):
            orchestrate.run("source", {"china-model-builder": "target"})
        client.beta.agents.sessions.steer.assert_called_once_with(
            agent_id="target", input="Build DCF"
        )


if __name__ == "__main__":
    unittest.main()
