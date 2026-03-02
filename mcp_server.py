#!/usr/bin/env python3
"""
MCP server for TV dashboard control.

Thin client that exposes MCP tools for interacting with the Apple TV
dashboard server. All commands are forwarded as HTTP requests to the
Pi's tv-dashboard server (port 8766).

Tools:
  - wake_tv: Wake the Apple TV and switch TV input to it
  - sleep_tv: Put the Apple TV to sleep
  - tv_command: Send a remote control command (home, menu, play, etc.)
  - now_playing: Get metadata about what's currently playing
  - list_apps: List installed apps on the Apple TV
  - launch_app: Launch an app by bundle ID
  - play_url: Stream a URL via AirPlay
  - volume: Control volume (up, down, or set level)
  - get_dashboard: Fetch current dashboard data (todo, grocery, reminders, activity)
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


def _text(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=msg)]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="wake_tv",
            description="Wake the Apple TV from sleep and switch the TV input to it.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="sleep_tv",
            description="Put the Apple TV to sleep.",
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
            name="now_playing",
            description=(
                "Get metadata about what's currently playing on the Apple TV — "
                "title, artist, album, app, media type, playback position, etc."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="list_apps",
            description="List all installed apps on the Apple TV with their bundle IDs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="launch_app",
            description=(
                "Launch an app on the Apple TV by its bundle ID. "
                "Use list_apps to find available bundle IDs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "app_id": {
                        "type": "string",
                        "description": "The bundle ID of the app to launch.",
                    },
                },
                "required": ["app_id"],
            },
        ),
        types.Tool(
            name="play_url",
            description="Stream a URL on the Apple TV via AirPlay (video, audio, or image).",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to stream.",
                    },
                },
                "required": ["url"],
            },
        ),
        types.Tool(
            name="volume",
            description="Control Apple TV volume: step up, step down, or set to a specific level (0–100).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["up", "down", "set"],
                        "description": "Volume action: 'up', 'down', or 'set'.",
                    },
                    "level": {
                        "type": "number",
                        "description": "Volume level (0–100). Required when action is 'set'.",
                    },
                },
                "required": ["action"],
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
            return _text("Apple TV woken and focused.")
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "sleep_tv":
        result = _post("/tv/sleep")
        if result.get("ok"):
            return _text("Apple TV is now sleeping.")
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "tv_command":
        cmd = arguments.get("command", "").strip()
        if not cmd:
            return _text("No command specified.")
        result = _post("/tv/command", {"command": cmd})
        if result.get("ok"):
            return _text(f"Sent: {cmd}")
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "now_playing":
        result = _get("/tv/now_playing")
        if result.get("ok"):
            lines = []
            lines.append(f"State: {result.get('device_state', 'unknown')}")
            if result.get("title"):
                lines.append(f"Title: {result['title']}")
            if result.get("artist"):
                lines.append(f"Artist: {result['artist']}")
            if result.get("album"):
                lines.append(f"Album: {result['album']}")
            if result.get("genre"):
                lines.append(f"Genre: {result['genre']}")
            if result.get("series_name"):
                lines.append(f"Series: {result['series_name']}")
            if result.get("season_number") is not None:
                lines.append(f"Season: {result['season_number']}")
            if result.get("episode_number") is not None:
                lines.append(f"Episode: {result['episode_number']}")
            if result.get("total_time") is not None:
                pos = result.get("position") or 0
                total = result["total_time"]
                lines.append(f"Progress: {pos}s / {total}s")
            if result.get("media_type"):
                lines.append(f"Media type: {result['media_type']}")
            return _text("\n".join(lines))
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "list_apps":
        result = _get("/tv/apps")
        if result.get("ok"):
            apps = result.get("apps", [])
            if not apps:
                return _text("No apps found.")
            lines = [f"- {a['name']} ({a['id']})" for a in apps]
            return _text("\n".join(lines))
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "launch_app":
        app_id = arguments.get("app_id", "").strip()
        if not app_id:
            return _text("No app_id specified.")
        result = _post("/tv/launch", {"app_id": app_id})
        if result.get("ok"):
            return _text(f"Launched: {app_id}")
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "play_url":
        url = arguments.get("url", "").strip()
        if not url:
            return _text("No URL specified.")
        result = _post("/tv/play_url", {"url": url})
        if result.get("ok"):
            return _text(f"Playing: {url}")
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "volume":
        action = arguments.get("action", "").strip()
        body = {"action": action}
        if action == "set":
            level = arguments.get("level")
            if level is None:
                return _text("No level specified for 'set' action.")
            body["level"] = level
        result = _post("/tv/volume", body)
        if result.get("ok"):
            return _text(result.get("message", "Done"))
        return _text(f"Failed: {result.get('error', 'unknown')}")

    elif name == "get_dashboard":
        result = _get("/tv/dashboard")
        if "sections" in result:
            lines = []
            for section in result["sections"]:
                lines.append(f"## {section['title']} ({len(section['items'])} items)")
                for item in section["items"]:
                    subtitle = f" — {item['subtitle']}" if item.get("subtitle") else ""
                    lines.append(f"  - {item['title']}{subtitle}")
            return _text("\n".join(lines))
        return _text(f"Failed: {result.get('error', 'unknown')}")

    return _text(f"Unknown tool: {name}")


async def main():
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
