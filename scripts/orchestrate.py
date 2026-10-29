#!/usr/bin/env python3
"""Reference event loop for cross-agent handoffs between managed agents.

REFERENCE ONLY — replace with your firm's workflow engine (Temporal, Airflow,
Guidewire event bus). This script shows the shape of the loop, not a
production implementation.

Security note: handoff requests are surfaced in the orchestrator's text output,
which is downstream of untrusted-document readers. An attacker who controls a
processed document could embed a literal handoff_request blob that, if echoed,
would be parsed here. This script mitigates by (a) hard-allowlisting
target_agent against the deployed slugs and (b) schema-validating the payload
before steering. Every candidate additionally requires an operator to type `yes`;
non-interactive runs fail closed. In production, prefer emitting handoffs via a
dedicated tool call or a typed SSE event the model cannot produce by quoting
document text.
"""
import json
import os
import re

import anthropic
import jsonschema

ALLOWED_TARGETS = {
    "china-pitch-agent", "china-market-researcher", "china-earnings-reviewer",
    "china-model-builder",
}

HANDOFF_PAYLOAD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["event"],
    "properties": {
        "event": {"type": "string", "maxLength": 2000},
        "context_ref": {"type": "string", "maxLength": 256,
                        "pattern": r"^[A-Za-z0-9 ._/:#-]+$"},
    },
}

HANDOFF_RE = re.compile(r'\{\s*"type"\s*:\s*"handoff_request"')


def extract_handoff(text: str) -> dict | None:
    for match in HANDOFF_RE.finditer(text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        target = obj.get("target_agent")
        payload = obj.get("payload")
        if target not in ALLOWED_TARGETS:
            continue
        try:
            jsonschema.validate(instance=payload, schema=HANDOFF_PAYLOAD_SCHEMA)
        except jsonschema.ValidationError:
            continue
        return {"target_agent": target, "payload": payload}
    return None


def confirm_handoff(target_slug: str) -> bool:
    try:
        answer = input(f"Authorize handoff to {target_slug}? Type 'yes' to continue: ")
    except (EOFError, OSError):
        return False
    return answer.strip().lower() == "yes"


def run(source_session_id: str, agent_ids: dict[str, str]) -> None:
    """agent_ids maps slug -> deployed CMA agent_id."""
    client = anthropic.Anthropic()
    # /v1/agents is a preview endpoint; SDK type stubs don't cover it yet.
    with client.beta.agents.sessions.stream(session_id=source_session_id) as stream:  # type: ignore[attr-defined]
        for event in stream:
            if event.type != "message_delta" or not getattr(event, "text", None):
                continue
            handoff = extract_handoff(event.text)
            if not handoff:
                continue
            target_slug = handoff["target_agent"]
            target_id = agent_ids.get(target_slug)
            if not target_id or not confirm_handoff(target_slug):
                continue
            client.beta.agents.sessions.steer(  # type: ignore[attr-defined]
                agent_id=target_id,
                input=handoff["payload"]["event"],
            )


if __name__ == "__main__":
    run(
        source_session_id=os.environ["SOURCE_SESSION_ID"],
        agent_ids=json.loads(os.environ.get("AGENT_IDS", "{}")),
    )
