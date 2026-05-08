import json
import os
import platform
import shlex
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

MCP_DIR = ".mcp"
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "version": "1.0",
    "servers": {}
}

_FASTMCP_TEMPLATE = '''\
from pathlib import Path

from mcp.server.fastmcp import FastMCP

BASE_DIR = Path(r"{project_path}")

mcp = FastMCP("{name}")


def _check_path(path: str) -> tuple[Path, str | None]:
    if path in ("", "/"):
        return BASE_DIR.resolve(), None
    target = (BASE_DIR / path).resolve()
    if not str(target).startswith(str(BASE_DIR.resolve())):
        return target, "Error: path is outside BASE_DIR"
    return target, None


@mcp.tool()
def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    target, err = _check_path(path)
    if err:
        return err
    if not target.is_file():
        return f"Error: not a file: {{path}}"
    return target.read_text()


@mcp.tool()
def list_directory(path: str) -> str:
    """List files and directories in a directory."""
    target, err = _check_path(path)
    if err:
        return err
    if not target.is_dir():
        return f"Error: not a directory: {{path}}"
    return "\\n".join(entry.name for entry in sorted(target.iterdir()))


@mcp.tool()
def search_content(path: str, query: str) -> list[str]:
    """Recursively search for files containing query, returning matching paths and lines."""
    target, err = _check_path(path)
    if err:
        return [err]
    if not target.is_dir():
        return [f"Error: not a directory: {{path}}"]
    results = []
    for file in target.rglob("*"):
        if file.is_file():
            try:
                for lineno, line in enumerate(file.read_text().splitlines(), 1):
                    if query in line:
                        results.append(f"{{file}}:{{lineno}}: {{line}}")
            except (OSError, UnicodeDecodeError):
                pass
    return results


if __name__ == "__main__":
    mcp.run()
'''


def _config_path(directory: Path) -> Path:
    return directory / MCP_DIR / CONFIG_FILE


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _wsl_distro_name() -> str:
    # WSL sets this in every session — fastest and most reliable source.
    name = os.environ.get("WSL_DISTRO_NAME", "").strip()
    if name:
        return name
    # Fallback: parse wsl.exe -l -q (output is UTF-16 LE on Windows).
    try:
        result = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            capture_output=True, timeout=5,
        )
        text = result.stdout.decode("utf-16-le", errors="ignore")
        distros = [ln.strip("\x00").strip() for ln in text.splitlines() if ln.strip("\x00").strip()]
        if distros:
            return distros[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    raise RuntimeError("Could not determine WSL distro name")


_RESOLVE_COMMANDS = {"uvx", "python", "python3"}


def _which_in_wsl(command: str) -> str:
    try:
        result = subprocess.run(
            ["which", command],
            capture_output=True, text=True, timeout=5,
        )
        resolved = result.stdout.strip()
        if result.returncode == 0 and resolved:
            return resolved
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return command


def _find_mcp_venv(args: list[str]) -> "Path | None":
    server_file = next((Path(a) for a in args if a.endswith(".py")), None)
    candidates = [Path.home() / "tools" / "mcp" / "venv"]
    if server_file:
        candidates += [server_file.parent / ".venv", server_file.parent / "venv"]
    for venv in candidates:
        lib = venv / "lib"
        if lib.is_dir() and any(lib.glob("python*/site-packages/mcp")):
            return venv
    return None


def _wrap_for_wsl(cfg: dict, distro: str) -> dict:
    command = cfg["command"]
    args = cfg.get("args", [])
    expanded_args = [str(Path(a).expanduser()) if a.startswith("~") else a for a in args]

    shell_cmd = None
    if command in {"python", "python3"}:
        venv = _find_mcp_venv(args)
        if venv:
            shell_cmd = f"source {venv.expanduser()}/bin/activate && python {shlex.join(expanded_args)}"

    if shell_cmd is None:
        if command.startswith("source "):
            shell_cmd = command
        elif command == "source":
            shell_cmd = " ".join(shlex.quote(a) if a != "&&" else "&&" for a in [command, *expanded_args])
        else:
            if command in _RESOLVE_COMMANDS:
                command = _which_in_wsl(command)
            shell_cmd = shlex.join([command, *expanded_args])

    return {**cfg, "command": "wsl.exe", "args": ["-d", distro, "-e", "bash", "-lc", shell_cmd]}


def _unwrap_wsl(cfg: dict) -> "dict | None":
    if cfg.get("command") != "wsl.exe":
        return None
    args = cfg.get("args", [])
    if "-lc" not in args:
        return None
    shell_cmd = args[args.index("-lc") + 1]
    if shell_cmd.startswith("source ") and " && " in shell_cmd:
        _, _, rest = shell_cmd.partition(" && ")
        tokens = shlex.split(rest)
    else:
        tokens = shlex.split(shell_cmd)
    if tokens and tokens[0] == "bash" and "-c" in tokens:
        tokens = shlex.split(tokens[tokens.index("-c") + 1])
    if not tokens:
        return None
    command, *cmd_args = tokens
    return {**cfg, "command": command, "args": cmd_args}


def _wsl_claude_desktop_config_path() -> "tuple[Path, list[str]]":
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "echo", "%USERNAME%"],
            capture_output=True, text=True, timeout=5,
        )
        windows_user = result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        windows_user = ""

    if not windows_user or windows_user == "%USERNAME%":
        raise RuntimeError("Could not determine Windows username from cmd.exe")

    standard = Path(f"/mnt/c/Users/{windows_user}/AppData/Roaming/Claude/claude_desktop_config.json")
    store_glob = f"/mnt/c/Users/{windows_user}/AppData/Local/Packages/Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"
    if standard.exists():
        return standard, [str(standard)]
    store_matches = sorted(Path(f"/mnt/c/Users/{windows_user}/AppData/Local/Packages").glob(
        "Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"
    ))
    if store_matches:
        return store_matches[0], [str(standard), str(store_matches[0])]
    return standard, [str(standard), store_glob]


def _claude_desktop_config_path() -> "tuple[Path, list[str]]":
    system = platform.system()
    if system == "Darwin":
        p = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        return p, [str(p)]
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        localappdata = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        standard = Path(appdata) / "Claude" / "claude_desktop_config.json"
        store_glob = str(Path(localappdata) / "Packages" / "Claude_*" / "LocalCache" / "Roaming" / "Claude" / "claude_desktop_config.json")
        if standard.exists():
            return standard, [str(standard)]
        store_matches = sorted(Path(localappdata).glob(
            "Packages/Claude_*/LocalCache/Roaming/Claude/claude_desktop_config.json"
        ))
        if store_matches:
            return store_matches[0], [str(standard), str(store_matches[0])]
        return standard, [str(standard), store_glob]
    if _is_wsl():
        return _wsl_claude_desktop_config_path()
    p = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    return p, [str(p)]


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        console.print(
            "[red]No MCP config found.[/red] "
            "Run [bold]arcmesh mcp init[/bold] first."
        )
        raise click.Abort()
    try:
        return json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]Failed to parse config:[/red] {exc}")
        raise click.Abort()


def _save_config(config_path: Path, config: dict) -> None:
    config_path.write_text(json.dumps(config, indent=2) + "\n")


@click.group()
def mcp():
    """Turn your project into an AI workspace:

    \b
      mcp setup

    \b
    Advanced:
      mcp add     Add custom MCP server
      mcp sync    Sync servers to Claude Desktop
      mcp status  Show active servers
    """


@mcp.command("init")
@click.option("--force", is_flag=True, help="Overwrite existing config.")
def init(force: bool):
    """Initialize MCP config in the current directory."""
    cwd = Path.cwd()
    config_path = _config_path(cwd)

    if config_path.exists() and not force:
        console.print(
            f"[yellow]Config already exists:[/yellow] {config_path}\n"
            "Use [bold]--force[/bold] to overwrite."
        )
        raise click.Abort()

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")

    console.print(f"[green]✓[/green] Initialized MCP config at [bold]{config_path}[/bold]")

    try:
        desktop_path, _ = _claude_desktop_config_path()
    except RuntimeError as exc:
        console.print(f"\n[red]Could not locate Claude Desktop config:[/red] {exc}")
        return

    if desktop_path.exists():
        console.print(
            f"\n[green]✓[/green] Claude Desktop config found:\n"
            f"  [bold]{desktop_path}[/bold]"
        )
    else:
        console.print(
            f"\n[yellow]![/yellow] Claude Desktop config not found.\n"
            f"  Expected at: [dim]{desktop_path}[/dim]"
        )


def _add_wizard(name: str, servers: dict, config_path: Path, config: dict) -> None:
    import questionary

    server_type = questionary.select(
        "Server type:",
        choices=["Remote (URL)", "Local script (existing)", "Local script (new)"],
    ).ask()
    if server_type is None:
        raise click.Abort()

    if server_type == "Remote (URL)":
        url = questionary.text("URL:").ask()
        if url is None:
            raise click.Abort()
        entry = {"command": "url", "args": [url]}

    elif server_type == "Local script (existing)":
        path = questionary.path("Path to script:").ask()
        if path is None:
            raise click.Abort()
        if not Path(path).exists():
            console.print(f"[red]File not found:[/red] {path}")
            raise click.Abort()
        entry = {"command": "python", "args": [path]}

    else:  # Local script (new)
        path = questionary.path("Output path:", default=f"{name}_server.py").ask()
        if path is None:
            raise click.Abort()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_FASTMCP_TEMPLATE.format(name=name, project_path=Path.cwd()))
        console.print(f"[green]✓[/green] Created [bold]{out}[/bold]")
        entry = {"command": "python", "args": [str(out.resolve())]}

    servers[name] = entry
    _save_config(config_path, config)

    args_display = " ".join(entry["args"]) if entry["args"] else "[dim]none[/dim]"
    console.print(
        f"[green]✓[/green] Added server [bold]{name}[/bold]\n"
        f"  command: [cyan]{entry['command']}[/cyan]\n"
        f"  args:    {args_display}"
    )


@mcp.command("add", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
@click.argument("name")
@click.argument("command", required=False, default=None)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def add(name: str, command: str | None, args: tuple[str, ...]):
    """Add a server to the MCP config.

    \b
    Without a command, starts an interactive wizard.

    Example:
      mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
    """
    config_path = _config_path(Path.cwd())
    config = _load_config(config_path)

    servers: dict = config.setdefault("servers", {})

    if name in servers:
        console.print(
            f"[yellow]Server [bold]{name}[/bold] already exists.[/yellow] "
            "Remove it from [bold].mcp/config.json[/bold] first."
        )
        raise click.Abort()

    if command is None:
        _add_wizard(name, servers, config_path, config)
        return

    servers[name] = {"command": command, "args": list(args)}
    _save_config(config_path, config)

    args_display = " ".join(args) if args else "[dim]none[/dim]"
    console.print(
        f"[green]✓[/green] Added server [bold]{name}[/bold]\n"
        f"  command: [cyan]{command}[/cyan]\n"
        f"  args:    {args_display}"
    )


@mcp.command("remove")
@click.argument("name")
def remove(name: str):
    """Remove a server from the MCP config."""
    config_path = _config_path(Path.cwd())
    config = _load_config(config_path)

    servers: dict = config.get("servers", {})

    if name not in servers:
        console.print(f"[red]Server [bold]{name}[/bold] not found in config.[/red]")
        raise click.Abort()

    del servers[name]
    _save_config(config_path, config)

    console.print(f"[green]✓[/green] Removed server [bold]{name}[/bold]")


@mcp.command("sync")
@click.option("--force", is_flag=True, help="Overwrite servers that already exist in Claude Desktop config.")
def sync(force: bool):
    """Sync servers from .mcp/config.json into Claude Desktop config."""
    config_path = _config_path(Path.cwd())
    config = _load_config(config_path)

    try:
        desktop_path, _ = _claude_desktop_config_path()
    except RuntimeError as exc:
        console.print(f"[red]Could not locate Claude Desktop config:[/red] {exc}")
        raise click.Abort()

    if not desktop_path.exists():
        console.print(
            f"[red]Claude Desktop config not found.[/red]\n"
            f"  Expected at: [dim]{desktop_path}[/dim]"
        )
        raise click.Abort()

    desktop_config = _load_config(desktop_path)
    mcp_servers: dict = desktop_config.setdefault("mcpServers", {})
    local_servers: dict = config.get("servers", {})

    if not local_servers:
        console.print("[dim]No servers in .mcp/config.json — nothing to sync.[/dim]")
        return

    wsl = _is_wsl()
    if wsl:
        try:
            distro = _wsl_distro_name()
        except RuntimeError as exc:
            console.print(f"[red]Could not determine WSL distro name:[/red] {exc}")
            raise click.Abort()

    synced, skipped = [], []
    for name, cfg in local_servers.items():
        if name in mcp_servers and not force:
            skipped.append(name)
        else:
            mcp_servers[name] = _wrap_for_wsl(cfg, distro) if wsl else cfg
            synced.append(name)

    _save_config(desktop_path, desktop_config)

    if synced:
        names = ", ".join(f"[bold]{n}[/bold]" for n in synced)
        suffix = f" [dim](wrapped for WSL distro {distro})[/dim]" if wsl else ""
        console.print(f"[green]✓[/green] Synced {len(synced)} server(s) to Claude Desktop: {names}{suffix}")
    if skipped:
        names = ", ".join(f"[bold]{n}[/bold]" for n in skipped)
        console.print(
            f"[yellow]![/yellow] Skipped {len(skipped)} existing server(s): {names}\n"
            "  Use [bold]--force[/bold] to overwrite."
        )


@mcp.command("unwrap")
@click.option("--force", is_flag=True, help="Overwrite servers that already exist in .mcp/config.json.")
def unwrap(force: bool):
    """Import WSL-wrapped servers from Claude Desktop config into .mcp/config.json."""
    try:
        desktop_path, _ = _claude_desktop_config_path()
    except RuntimeError as exc:
        console.print(f"[red]Could not locate Claude Desktop config:[/red] {exc}")
        raise click.Abort()

    if not desktop_path.exists():
        console.print(
            f"[red]Claude Desktop config not found.[/red]\n"
            f"  Expected at: [dim]{desktop_path}[/dim]"
        )
        raise click.Abort()

    desktop_config = _load_config(desktop_path)
    mcp_servers: dict = desktop_config.get("mcpServers", {})

    config_path = _config_path(Path.cwd())
    config = _load_config(config_path)
    servers: dict = config.setdefault("servers", {})

    imported, skipped, not_wrapped = [], [], []
    for name, cfg in mcp_servers.items():
        unwrapped = _unwrap_wsl(cfg)
        if unwrapped is None:
            not_wrapped.append(name)
            continue
        if name in servers and not force:
            skipped.append(name)
        else:
            servers[name] = unwrapped
            imported.append(name)

    _save_config(config_path, config)

    if not mcp_servers:
        console.print("[dim]No servers found in Claude Desktop config.[/dim]")
        return
    if imported:
        names = ", ".join(f"[bold]{n}[/bold]" for n in imported)
        console.print(f"[green]✓[/green] Imported {len(imported)} server(s): {names}")
    if skipped:
        names = ", ".join(f"[bold]{n}[/bold]" for n in skipped)
        console.print(
            f"[yellow]![/yellow] Skipped {len(skipped)} existing server(s): {names}\n"
            "  Use [bold]--force[/bold] to overwrite."
        )
    if not_wrapped:
        names = ", ".join(f"[bold]{n}[/bold]" for n in not_wrapped)
        console.print(f"[dim]Skipped {len(not_wrapped)} non-wrapped server(s): {names}[/dim]")


@mcp.command("setup")
@click.option("--force", is_flag=True, help="Overwrite existing setup.")
@click.option("--verbose", is_flag=True, help="Print each internal step.")
@click.option("--config-path", "desktop_config_path", default=None, metavar="PATH",
              type=click.Path(path_type=Path),
              help="Path to Claude Desktop config file (overrides auto-detection).")
def setup(force: bool, verbose: bool, desktop_config_path: "Path | None"):
    """Initialize an AI workspace with MCP server for the current project."""
    cwd = Path.cwd()
    project_name = cwd.name
    config_path = _config_path(cwd)
    server_path = cwd / MCP_DIR / "server.py"

    if config_path.exists() and not force:
        console.print(
            "[green]✅ Already set up[/green]\n\n"
            "AI workspace is ready. Try asking Claude:\n"
            '  "Explain this repo"\n'
            '  "Find all API endpoints"\n'
            '  "Where is authentication handled?"'
        )
        return

    if verbose:
        console.print(f"[dim]Creating {config_path}[/dim]")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")

    if verbose:
        console.print(f"[dim]Generating {server_path}[/dim]")
    server_path.write_text(_FASTMCP_TEMPLATE.format(name=project_name, project_path=cwd))

    if verbose:
        console.print(f"[dim]Adding server '{project_name}' to .mcp/config.json[/dim]")
    config = json.loads(config_path.read_text())
    config.setdefault("servers", {})[project_name] = {
        "command": "python",
        "args": [str(server_path)],
    }
    _save_config(config_path, config)

    desktop_found = False
    desktop_updated = False
    checked_paths: list[str] = []

    if desktop_config_path is not None:
        desktop_path: "Path | None" = desktop_config_path
        desktop_found = desktop_path.exists()
    else:
        try:
            desktop_path, checked_paths = _claude_desktop_config_path()
            desktop_found = desktop_path.exists()
        except RuntimeError:
            desktop_path = None
            desktop_found = False

    if desktop_found:
        if verbose:
            console.print(f"[dim]Syncing to Claude Desktop config at {desktop_path}[/dim]")
        try:
            desktop_config = json.loads(desktop_path.read_text())
        except (json.JSONDecodeError, OSError):
            desktop_config = None

        if desktop_config is not None:
            mcp_servers = desktop_config.setdefault("mcpServers", {})
            entry: dict = {"command": "python", "args": [str(server_path)]}
            if _is_wsl():
                try:
                    distro = _wsl_distro_name()
                    entry = _wrap_for_wsl(entry, distro)
                    if verbose:
                        console.print(f"[dim]Wrapped for WSL distro: {distro}[/dim]")
                except RuntimeError:
                    pass
            if force or project_name not in mcp_servers:
                mcp_servers[project_name] = entry
                _save_config(desktop_path, desktop_config)
            desktop_updated = True
    elif verbose:
        console.print("[dim]Claude Desktop config not found, skipping sync[/dim]")

    # Sanity checks
    if not config_path.exists():
        console.print(
            "[red]❌ Setup incomplete[/red]\n\n"
            "Reason:\n  Internal error writing config\n\n"
            "Fix:\n  Check write permissions for the current directory"
        )
        return
    if not server_path.exists():
        console.print(
            "[red]❌ Setup incomplete[/red]\n\n"
            "Reason:\n  Internal error writing server script\n\n"
            "Fix:\n  Check write permissions for the .mcp/ directory"
        )
        return
    if not desktop_found:
        if desktop_config_path is not None:
            console.print(
                "[red]❌ Setup incomplete[/red]\n\n"
                f"Reason:\n  Config not found at specified path:\n    {desktop_config_path}\n\n"
                "Fix:\n  Check the path and try again"
            )
        else:
            paths_lines = "".join(f"\n    {p}" for p in checked_paths) if checked_paths else (f"\n    {desktop_path}" if desktop_path else "")
            console.print(
                "[red]❌ Setup incomplete[/red]\n\n"
                f"Reason:\n  Claude Desktop config not found\n\n"
                f"Paths checked:{paths_lines}\n\n"
                "Fix:\n"
                "  • If Claude Desktop is not installed, install it and open it at least once\n"
                "  • If it is already installed, open Claude Desktop to generate its config\n"
                "  • Or specify the config location manually:\n"
                '      arcmesh mcp setup --config-path "/path/to/claude_desktop_config.json"'
            )
        return
    if not desktop_updated:
        console.print(
            "[red]❌ Setup incomplete[/red]\n\n"
            "Reason:\n  Could not write to Claude Desktop config\n\n"
            "Fix:\n  Check that the Claude Desktop config file is valid JSON and is writable"
        )
        return

    console.print(f"\n[green]✅ AI workspace ready[/green]\n")
    console.print(f"Project:    {project_name}")
    console.print(f"MCP server: .mcp/server.py")
    console.print(f"\nNext steps:")
    console.print(f"  1. Restart Claude Desktop")
    console.print(f"  2. Open this folder in Claude Desktop")
    console.print(f"\nTry asking:")
    console.print(f'  "Explain this repo"')
    console.print(f'  "Find all API endpoints"')
    console.print(f'  "Where is authentication handled?"')


@mcp.command("status")
def status():
    """Show active MCP servers from local config."""
    cwd = Path.cwd()
    config_path = _config_path(cwd)
    config = _load_config(config_path)

    servers: dict = config.get("servers", {})

    console.print(f"[dim]Config:[/dim] {config_path.relative_to(Path.cwd())}\n")

    if not servers:
        console.print("[dim]No servers configured.[/dim]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Command")
    table.add_column("Args")
    table.add_column("Env vars")

    for name, cfg in servers.items():
        command = cfg.get("command", "[dim]—[/dim]")
        args = " ".join(cfg.get("args", [])) or "[dim]—[/dim]"
        env_count = len(cfg.get("env", {}))
        env_display = str(env_count) if env_count else "[dim]—[/dim]"
        table.add_row(name, command, args, env_display)

    console.print(table)
