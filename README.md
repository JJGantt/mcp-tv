# mcp-tv

MCP server for Apple TV dashboard control. Exposes tools for waking the Apple TV, sending remote commands, and reading dashboard data.

## Overview

**mcp-tv** is a thin MCP client that forwards commands to the [tv-dashboard](https://github.com/JJGantt/tv-dashboard) server on the Pi. Install it on any machine where Claude runs — Mac, Pi, etc.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `wake_tv` | Wake the Apple TV from sleep and switch TV input to it |
| `tv_command(command)` | Send a remote control command (home, menu, play, pause, etc.) |
| `get_dashboard` | Fetch current dashboard data (todo, grocery, reminders, activity) |

## Setup

1. Clone the repo
2. Copy `config.example.json` → `config.json` and set your Pi's IPs
3. Register in Claude's MCP config (e.g. `~/.claude.json`)

## Configuration

`config.json` (gitignored):

```json
{
  "tv_server_urls": [
    "http://10.0.0.14:8766",
    "http://100.104.197.58:8766"
  ],
  "request_timeout": 10
}
```

Multiple URLs are tried in order — local IP first, Tailscale fallback.

## Related

- **Server:** [tv-dashboard](https://github.com/JJGantt/tv-dashboard) — Pi-side Flask server with pyatv Apple TV control
- **Client:** [TVDashboard](https://github.com/JJGantt/TVDashboard) — tvOS app
