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

BASE_DIR = Path("{project_path}")

mcp = FastMCP("{name}")


def _check_path(path: str) -> tuple[Path, str | None]:
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
def list_directory(path: str) -> list[str]:
    """List files and directories in a directory."""
    target, err = _check_path(path)
    if err:
        return [err]
    if not target.is_dir():
        return [f"Error: not a directory: {{path}}"]
    return [entry.name for entry in sorted(target.iterdir())]


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


def _wsl_claude_desktop_config_path() -> Path:
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

    return Path(f"/mnt/c/Users/{windows_user}/AppData/Roaming/Claude/claude_desktop_config.json")


def _claude_desktop_config_path() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if system == "Windows":
        appdata = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    if _is_wsl():
        return _wsl_claude_desktop_config_path()
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


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
    """Manage MCP (Model Context Protocol) servers."""


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
        desktop_path = _claude_desktop_config_path()
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
        desktop_path = _claude_desktop_config_path()
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
        desktop_path = _claude_desktop_config_path()
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
