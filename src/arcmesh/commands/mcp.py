import json
import os
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


@mcp.command("status")
def status():
    """Show active MCP servers from local config."""
    cwd = Path.cwd()
    config_path = _config_path(cwd)

    if not config_path.exists():
        console.print(
            "[yellow]No MCP config found.[/yellow] "
            "Run [bold]arcmesh mcp init[/bold] to create one."
        )
        return

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        console.print(f"[red]Failed to parse config:[/red] {exc}")
        raise click.Abort()

    servers: dict = config.get("servers", {})

    console.print(f"[dim]Config:[/dim] {config_path}\n")

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
