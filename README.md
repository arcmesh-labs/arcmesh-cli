# ArcMesh CLI

**One command. Your codebase, AI-ready.**

```bash
pip install arcmesh
cd your-project
arcmesh mcp setup
```

Restart Claude Desktop. Done.

---

## What it does

ArcMesh creates a local MCP server for your project and connects it to Claude Desktop automatically.

No config files. No decisions. No path issues.

```bash
✅ AI workspace ready

Project:    your-project
MCP server: .mcp/server.py

Next steps:
  1. Restart Claude Desktop
  2. Open this folder in Claude Desktop

Try asking:
  "Explain this repo"
  "Find all API endpoints"
  "Where is authentication handled?"
```

---

## Requirements

- Python 3.10+
- Claude Desktop
- Mac, Windows, or WSL

---

## Advanced

Most people never need this. But if you want full control:

| Command | What it does |
|---|---|
| `arcmesh mcp init` | Initialize config without generating a server |
| `arcmesh mcp add` | Add a custom MCP server (wizard or inline) |
| `arcmesh mcp sync` | Push local config to Claude Desktop |
| `arcmesh mcp status` | Show configured servers |
| `arcmesh mcp remove` | Remove a server |
| `arcmesh mcp unwrap` | Import WSL-wrapped servers back to local config |

Run `arcmesh mcp --help` to see everything.

---

## Philosophy

There should be one default way to make a codebase AI-ready.

One command. No decisions.

---

## License

MIT