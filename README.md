# ArcMesh CLI

Turn any repo into something AI can understand in 10 seconds.

---

## Install & Setup

**From PyPI:**
```bash
pip install arcmesh
```

**From GitHub :**
```
pip install git+https://github.com/arcmesh-labs/arcmesh-cli.git
```

Use it in any project
```bash
cd your-project
mcp setup
```
Restart Claude Desktop.

---

## After setup

Your codebase is now accessible to Claude.

Try asking:

* "Explain this repo"
* "Find all API endpoints"
* "Where is authentication handled?"
* "What does this project do?"

---

## What this gives you

Instead of manually wiring AI to your codebase, ArcMesh does it automatically.

One command:

### your project → AI-readable workspace

---
## How it works (simple)

ArcMesh creates a local MCP server for your project and connects it to Claude Desktop automatically.

No configuration. No decisions.

## Output example
```bash
✅ AI workspace ready

Project:    your-project
MCP server: .mcp/server.py

Next steps:
  1. Restart Claude Desktop
  2. Open this folder

Try asking:
  "Explain this repo"
  ```
---
## Why this exists

Connecting AI to a codebase today usually requires:

* manual MCP setup
* config files
* path issues
* repetitive per-project setup

ArcMesh removes all of that.

---

## Requirements
* Python 3.10+
* Claude Desktop
* Mac, Windows, or WSL

---

## Advanced

Most people never need this. But if you want full control:

| Command | What it does |
|---|---|
| `mcp init` | Initialize config without generating a server |
| `mcp add` | Add a custom MCP server (wizard or inline) |
| `mcp sync` | Push local config to Claude Desktop |
| `mcp status` | Show configured servers |
| `mcp remove` | Remove a server |
| `mcp unwrap` | Import WSL-wrapped servers back to local config |

Run `mcp --help` to see everything.

---
## Philosophy

There should be one default way to make a codebase AI-ready:

### One command. No decisions.

---

## License

MIT