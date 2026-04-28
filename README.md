# ArcMesh CLI

Manage and sync MCP server configurations from the command line.

## Why ArcMesh

Claude Desktop (and other MCP clients) store server configs in a global JSON file buried in your OS app-data directory. Hand-editing it is error-prone, not version-controlled, and painful in WSL where every command needs wrapping in `wsl.exe`. ArcMesh keeps a `.mcp/config.json` in your project as the source of truth and syncs it on demand.

## Installation

**From PyPI:**
```
pip install arcmesh
```

**From GitHub (latest):**
```
pip install git+https://github.com/arcmesh-labs/arcmesh-cli.git
```

Both `arcmesh` and `mcp` are registered as entry points — the commands below work with either prefix.

> **Windows note:** The `mcp` shorthand may conflict with the `mcp` package's own CLI. If you get unexpected errors, use `arcmesh mcp <command>` instead. For example: `arcmesh mcp init`, `arcmesh mcp add`, `arcmesh mcp sync`.

---

## Quick start — local repo in 4 steps

```bash
pip install git+https://github.com/arcmesh-labs/arcmesh-cli.git
cd my-project
arcmesh mcp init
arcmesh mcp add my-project   # choose "Local script (new)"
arcmesh mcp sync
```

Restart Claude Desktop — it can now read, list, and search files in your project.

---

## Commands

### `mcp init`

Creates `.mcp/config.json` in the current directory and reports whether Claude Desktop's config file was found.

```
$ mcp init
✓ Initialized MCP config at /your/project/.mcp/config.json

✓ Claude Desktop config found:
  /home/you/.config/Claude/claude_desktop_config.json
```

Use `--force` to reinitialize an existing config.

---

### `mcp add <name> [command] [args...]`

Adds a server entry to `.mcp/config.json`.

If `command` is omitted, an interactive wizard starts and guides you through three options:

**Remote (URL)** — connects to an external MCP server by URL.

**Local script (existing)** — points to an existing `.py` file on disk.

**Local script (new)** — generates a ready-to-use `server.py` in your project with three tools: `read_file`, `list_directory`, and `search_content`, all scoped to your project folder. This is the recommended starting point for giving Claude Desktop access to a local repo.

```
$ mcp add my-repo
? Server type: Local script (new)
? Output path: my-repo_server.py
✓ Created /your/project/my-repo_server.py
✓ Added server my-repo
```

You can also pass arguments directly to skip the wizard:

```
$ mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
$ mcp add github uvx mcp-server-github
$ mcp add myserver python ~/tools/mcp/servers/myserver.py
```

Fails if a server with that name already exists.

---

### `mcp remove <name>`

Removes a server from `.mcp/config.json`.

```
$ mcp remove filesystem
✓ Removed server filesystem
```

Fails if the name is not found.

---

### `mcp status`

Lists all servers in the local `.mcp/config.json`.

```
$ mcp status
Config: .mcp/config.json

╭──────────┬─────────┬──────────────────────────────────┬──────────╮
│ Name     │ Command │ Args                             │ Env vars │
├──────────┼─────────┼──────────────────────────────────┼──────────┤
│ github   │ uvx     │ mcp-server-github                │ —        │
│ myserver │ python  │ ~/tools/mcp/servers/myserver.py  │ —        │
╰──────────┴─────────┴──────────────────────────────────┴──────────╯
```

---

### `mcp sync`

Writes all servers from `.mcp/config.json` into the `mcpServers` key of Claude Desktop's config. Other keys are left untouched.

```
$ mcp sync
✓ Synced 2 server(s) to Claude Desktop: github, myserver
```

Use `--force` to overwrite servers that already exist in Claude Desktop's config.

**WSL auto-detection:** when running in WSL, `sync` automatically wraps every command with `wsl.exe -d <distro> -e bash -lc ...` so Claude Desktop (running on Windows) can launch them. For `python` and `python3` commands, ArcMesh also detects a suitable venv before wrapping (see below).

---

### `mcp unwrap`

Reads `mcpServers` from Claude Desktop's config and imports any `wsl.exe`-wrapped entries back into `.mcp/config.json`, reversing what `sync` produced. Useful for migrating manually-written entries or bootstrapping from an existing Claude Desktop setup.

```
$ mcp unwrap
✓ Imported 2 server(s): github, myserver
```

Entries that already exist in `.mcp/config.json` are skipped by default. Use `--force` to overwrite them. Non-wrapped entries are reported separately and left untouched.

```
$ mcp unwrap
✓ Imported 1 server(s): myserver
! Skipped 1 existing server(s): github
  Use --force to overwrite.
Skipped 1 non-wrapped server(s): filesystem
```

---

## WSL venv auto-detection

When `command` is `python` or `python3`, `sync` checks for a virtualenv containing the `mcp` package before building the wrapped command. Candidates are tested in this order:

| Priority | Path |
|---|---|
| 1 | `~/tools/mcp/venv` |
| 2 | `.venv` sibling to the server `.py` file |
| 3 | `venv` sibling to the server `.py` file |

If a valid venv is found, the sync output wraps the command as:

```
source /path/to/venv/bin/activate && python server.py [args...]
```

If no venv is found, `sync` falls back to resolving the full `python` path via `which` inside WSL.

---

## Claude Desktop config location

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| WSL (Windows host) | `/mnt/c/Users/<username>/AppData/Roaming/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |