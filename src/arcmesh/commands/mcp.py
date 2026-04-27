import json
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


def _config_path(directory: Path) -> Path:
    return directory / MCP_DIR / CONFIG_FILE


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


@mcp.command("add", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
@click.argument("name")
@click.argument("command")
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def add(name: str, command: str, args: tuple[str, ...]):
    """Add a server to the MCP config.

    \b
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
