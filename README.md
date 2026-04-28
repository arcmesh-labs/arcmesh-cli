# ArcMesh CLI

Manage and sync MCP server configurations from the command line.

## Why ArcMesh

Claude Desktop (and other MCP clients) store server configs in a global JSON file buried in your OS app-data directory. Hand-editing it is error-prone, not version-controlled, and painful in WSL where every command needs wrapping in `wsl.exe`. ArcMesh keeps a `.mcp/config.json` in your project as the source of truth and syncs it on demand.

## Installation

```
pip install arcmesh
```

Both `arcmesh` and `mcp` are registered as entry points — the commands below work with either prefix.

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

### `mcp add <name> <command> [args...]`

Adds a server entry to `.mcp/config.json`. Arguments after the command are passed through verbatim.

```
$ mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
✓ Added server filesystem
  command: npx
  args:    -y @modelcontextprotocol/server-filesystem /tmp

$ mcp add github uvx mcp-server-github
✓ Added server github
  command: uvx
  args:    mcp-server-github

$ mcp add myserver python ~/tools/mcp/servers/myserver.py
✓ Added server myserver
  command: python
  args:    ~/tools/mcp/servers/myserver.py
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

Writes all servers from `.mcp/config.json` into the `mcpServers` key of Claude Desktop's config. Other keys in the Claude Desktop config are left untouched.

```
$ mcp sync
✓ Synced 2 server(s) to Claude Desktop: github, myserver
```

Servers that already exist in the Claude Desktop config are skipped by default. Use `--force` to overwrite them:

```
$ mcp sync --force
✓ Synced 2 server(s) to Claude Desktop: github, myserver
```

**WSL auto-detection:** when running in WSL, `sync` automatically wraps every command with `wsl.exe -d <distro> -e bash -lc ...` so Claude Desktop (running on Windows) can launch them. For `python` and `python3` commands, ArcMesh also detects a suitable venv before wrapping (see below).

---

### `mcp unwrap`

Reads `mcpServers` from Claude Desktop's config and imports any `wsl.exe`-wrapped entries back into `.mcp/config.json`, reversing what `sync` produced. Useful for migrating manually-written entries or bootstrapping a project config from an existing Claude Desktop setup.

```
$ mcp unwrap
✓ Imported 2 server(s): github, myserver
```

Entries that already exist in `.mcp/config.json` are skipped by default. Use `--force` to overwrite them. Non-wrapped entries (those that don't use `wsl.exe`) are reported separately and left untouched.

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

A venv is considered valid if `<venv>/lib/python*/site-packages/mcp` exists. If a valid venv is found, the sync output wraps the command as:

```
source /path/to/venv/bin/activate && python server.py [args...]
```

If no venv is found, `sync` falls back to resolving the full `python` path via `which` inside WSL.

## Claude Desktop config location

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |
| WSL (Windows host) | `/mnt/c/Users/<username>/AppData/Roaming/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
