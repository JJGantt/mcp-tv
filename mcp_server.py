#!/usr/bin/env python3
"""
MCP server for TV dashboard control.

Thin client that exposes MCP tools for interacting with the Apple TV
dashboard server. All commands are forwarded as HTTP requests to the
Pi's tv-dashboard server (port 8766).

Tools:
  - wake_tv: Wake the Apple TV and switch TV input to it
  - tv_command: Send a remote control command (home, menu, play, etc.)
  - refresh_dashboard: Clear image cache and get fresh dashboard data
"""

import json
import urllib.request
import urllib.error
from pathlib import Path

from mcp.server import Server
import mcp.server.stdio
import mcp.types as types

_CONFIG_PATH = Path(__file__).parent / "config.json"


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"No config.json found at {_CONFIG_PATH}. "
            f"Copy config.example.json to config.json and fill in your values."
        )
    return json.loads(_CONFIG_PATH.read_text())


CONFIG = _load_config()
TV_URLS = CONFIG["tv_server_urls"]
TIMEOUT = CONFIG.get("request_timeout", 10)

server = Server("tv")


def _post(path: str, body: dict | None = None) -> dict:
    """POST to the tv-dashboard server. Tries each URL in order."""
    data = json.dumps(body or {}).encode()
    for base_url in TV_URLS:
        url = f"{base_url}{path}"
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return {"ok": False, "error": "Could not reach tv-dashboard server"}


def _get(path: str) -> dict:
    """GET from the tv-dashboard server. Tries each URL in order."""
    for base_url in TV_URLS:
        url = f"{base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return {"ok": False, "error": "Could not reach tv-dashboard server"}


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="wake_tv",
            description="Wake the Apple TV from sleep and switch the TV input to it.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="tv_command",
            description=(
                "Send a remote control command to the Apple TV. "
                "Available commands: home, menu, select, up, down, left, right, "
                "play, pause, play_pause, stop, next, previous, top_menu, "
                "screensaver, channel_up, channel_down."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The remote control command to send.",
                    },
                },
                "required": ["command"],
            },
        ),
        types.Tool(
            name="get_dashboard",
            description=(
                "Get the current TV dashboard data — all sections "
                "(todo, grocery, reminders, activity) with their items."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "wake_tv":
        result = _post("/tv/wake")
        if result.get("ok"):
            return [types.TextContent(type="text", text="Apple TV woken and focused.")]
        return [types.TextContent(type="text", text=f"Failed: {result.get('error', 'unknown')}")]

    elif name == "tv_command":
        cmd = arguments.get("command", "").strip()
        if not cmd:
            return [types.TextContent(type="text", text="No command specified.")]
        result = _post("/tv/command", {"command": cmd})
        if result.get("ok"):
            return [types.TextContent(type="text", text=f"Sent: {cmd}")]
        return [types.TextContent(type="text", text=f"Failed: {result.get('error', 'unknown')}")]

    elif name == "get_dashboard":
        result = _get("/tv/dashboard")
        if "sections" in result:
            lines = []
            for section in result["sections"]:
                lines.append(f"## {section['title']} ({len(section['items'])} items)")
                for item in section["items"]:
                    subtitle = f" — {item['subtitle']}" if item.get("subtitle") else ""
                    lines.append(f"  - {item['title']}{subtitle}")
            return [types.TextContent(type="text", text="\n".join(lines))]
        return [types.TextContent(type="text", text=f"Failed: {result.get('error', 'unknown')}")]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
