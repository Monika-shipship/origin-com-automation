from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _exercise_real_stdio_transport():
    plugin_root = Path(__file__).resolve().parents[2]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "origin_com_automation.server"],
        cwd=str(plugin_root),
    )
    async with stdio_client(parameters) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            health = await session.call_tool("origin_health_check", {})
            return tools, health


def test_real_stdio_transport_lists_expanded_tools_and_calls_health_check():
    tools, health = asyncio.run(_exercise_real_stdio_transport())
    by_name = {tool.name: tool for tool in tools.tools}

    assert "origin_recover_session" in by_name
    graph_options = by_name["origin_configure_graph"].inputSchema["properties"]["options"]
    assert "properties" in graph_options
    assert "categorical_style" in graph_options["properties"]
    assert health.isError is False
    assert health.structuredContent["success"] is True
