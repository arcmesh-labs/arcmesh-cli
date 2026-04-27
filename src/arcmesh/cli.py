import click
from rich.console import Console

from arcmesh.commands.mcp import mcp

console = Console()


@click.group()
@click.version_option(package_name="arcmesh")
def cli():
    """arcmesh — MCP configuration manager."""


cli.add_command(mcp)
