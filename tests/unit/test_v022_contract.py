import asyncio
import hashlib
import json

from origin_com_automation.server import create_server


BASELINE_TOOL_SCHEMA_SHA256 = "4a71f5de9fd3028375d56608c9d61cd32dd959bbdff757a031cb1ea645a5b9fc"


def _tool_contract() -> list[dict[str, object]]:
    tools = asyncio.run(create_server().list_tools())
    return [
        {"name": tool.name, "inputSchema": tool.inputSchema}
        for tool in sorted(tools, key=lambda item: item.name)
    ]


def test_v021_tool_surface_has_45_tools_and_stable_schema_digest():
    payload = _tool_contract()
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    assert len(payload) == 45
    assert hashlib.sha256(encoded).hexdigest() == BASELINE_TOOL_SCHEMA_SHA256
