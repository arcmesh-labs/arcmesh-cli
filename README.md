# arcmesh

CLI for managing MCP (Model Context Protocol) server configurations locally and syncing them to Claude Desktop.

## Installation

```
pip install arcmesh
```

Both `arcmesh` and `mcp` are registered as entry points — the commands below work with either prefix.

## Why arcmesh

Claude Desktop stores MCP server configs in a global JSON file buried in your OS app-data directory. Adding or removing a server means hand-editing that file, getting the schema right, and not accidentally clobbering other keys. arcmesh keeps a `.mcp/config.json` in your project directory as the source of truth and syncs it to Claude Desktop on demand.

## Commands

### `mcp init`

Creates `.mcp/config.json` in the current directory and reports whether Claude Desktop is installed.

```
$ mcp init
✓ Initialized MCP config at /your/project/.mcp/config.json

✓ Claude Desktop config found:
  /home/you/.config/Claude/claude_desktop_config.json
```

Use `--force` to reinitialize an existing config.

---

### `mcp add <name> <command> [args...]`

Adds a server entry to `.mcp/config.json`. Arguments after the command are passed through verbatim, including flags like `-y`.

```
$ mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
✓ Added server filesystem
  command: npx
  args:    -y @modelcontextprotocol/server-filesystem /tmp

$ mcp add github uvx mcp-server-github
✓ Added server github
  command: uvx
  args:    mcp-server-github
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

╭────────┬─────────┬───────────────────┬──────────╮
│ Name   │ Command │ Args              │ Env vars │
├────────┼─────────┼───────────────────┼──────────┤
│ github │ uvx     │ mcp-server-github │ —        │
╰────────┴─────────┴───────────────────┴──────────╯
```

---

### `mcp sync`

Writes all servers from `.mcp/config.json` into the `mcpServers` key of Claude Desktop's config. Other keys in the Claude Desktop config are left untouched.

```
$ mcp sync
✓ Synced 2 server(s) to Claude Desktop: filesystem, github
```

Servers that already exist in the Claude Desktop config are skipped by default:

```
$ mcp sync
✓ Synced 1 server(s) to Claude Desktop: filesystem
! Skipped 1 existing server(s): github
  Use --force to overwrite.
```

Use `--force` to overwrite existing entries.

Fails if `.mcp/config.json` or the Claude Desktop config does not exist.

## Claude Desktop config location

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux / WSL | `~/.config/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
